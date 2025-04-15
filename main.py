
from typing import *

from aiogram import types, Dispatcher, Bot, F, client
from aiogram.filters.command import Command
import asyncio
from aiogram.utils.keyboard import InlineKeyboardBuilder

import os
from dotenv import load_dotenv

import config
import engine
import random

# loading objects

load_dotenv()
TOKEN = os.getenv('TOKEN')

bot = Bot(TOKEN,
    default=client.default.DefaultBotProperties(
        parse_mode='html'
    )
)
dp = Dispatcher()

mg = engine.Manager()


# ---------------------------
# functions
# ---------------------------


async def game_start(id: int):
    game = mg.get_game(id)
    if game == None: return

    keyboard = InlineKeyboardBuilder()
    keyboard.add(types.InlineKeyboardButton(text='выбрать карту...', switch_inline_query_current_chat=''))

    await bot.edit_message_text(
        text = 'игра началась!',
        chat_id = game.chat,
        message_id = game.message, 
        reply_markup = keyboard.as_markup()
    )


async def card_used(id: int):
    game = mg.get_game(id)
    if game == None: return

    text = game.get_message_str()
    message = await bot.send_message(
        chat_id = game.chat,
        text = text, 
        reply_to_message_id = game.message
    )
    game.message = message.message_id


async def round_over(id: int):
    game = mg.get_game(id)
    if game == None: return

    text = game.get_message_str()
    message = await bot.send_message(
        chat_id = game.chat,
        text = text, 
        reply_to_message_id = game.message
    )
    game.message = message.message_id

    await asyncio.sleep(10)
    await game.new_round()


async def new_round(id: int):
    game = mg.get_game(id)
    if game == None: return

    text = game.get_message_str()
    message = await bot.send_message(
        chat_id = game.chat,
        text = text, 
        reply_to_message_id = game.message
    )
    game.message = message.message_id


async def game_over(id: int):
    game = mg.get_game(id)
    if game == None: return

    mg.games.pop(game.id)

    if not game.ready:
        await bot.edit_message_text(
            text = f'<b>а все</b>',
            chat_id = game.chat,
            message_id = game.message
        )
        return

    score = ''
    for i in game.players.values():
        score += f'{i.mention}: <code>{i.pts}</code>\n'

    await bot.edit_message_text(
        text = f'<b>конец игры</b>\n\nсчёт:\n{score}',
        chat_id = game.chat,
        message_id = game.message
    )


async def request_deny(id: int):
    game = mg.get_game(id)
    if game == None: return


mg.hooks = engine.Hooks(
    game_start=game_start,
    card_used=card_used,
    round_over=round_over,
    game_over=game_over,
    new_round=new_round,
    request_deny=request_deny
)

# ---------------------------
# commands
# ---------------------------

@dp.message(Command('invite'))
async def invite(msg: types.Message):
    '''
    Invite a player to play.
    '''
    player1 = msg.from_user.id

    if msg.reply_to_message is None:
        await msg.reply('ответь на сообщение того, с кем хочешь поиграть!')
        return

    player2 = msg.reply_to_message.from_user.id

    # filtering channel users and bots
    if player1 == 136817688: # @Channel_Bot
        await msg.reply(f'переключись на основной акк!')
        return
    
    if player1 == 1087968824:
        await msg.reply(f'убери анонимность админов в настройках группы!')
        return
    
    if player2 == 136817688: # @Channel_Bot
        await msg.reply(f'переключись на основной акк!')
        return

    if player2 == 1087968824:
        await msg.reply(f'надо убрать анонимность админов в настройках группы!')
        return

    if msg.reply_to_message.from_user.is_bot:
        await msg.reply(f'с ботом играть нельзя!')
        return

    if player1 == player2:
        await msg.reply(f'с самим собой играть нельзя!')
        return

    # checking chat type
    if msg.chat.type == 'private':
        await msg.reply('меня нужно использовать в группах!')
        return

    # checking if already playing
    if mg.get_game(player1):
        await msg.reply('ты уже играешь в игру!')
        return
    
    # keyboard
    keyboard = InlineKeyboardBuilder()

    keyboard.add(types.InlineKeyboardButton(
        text='принять',
        callback_data=f'accept:{player1}:{player2}'
    ))
    keyboard.add(types.InlineKeyboardButton(
        text='отменить',
        callback_data=f'deny:{player1}:{player2}'
    ))
        
    user = msg.reply_to_message.from_user
    mention = f'<a href="tg://user?id={user.id}">{user.full_name}</a>'
    message = await msg.reply(
        f'{mention}, тебя приглашают в игру в шульпека!\n\n'\
        'прочитай правила, если не знаешь как играть - <b>/rules</b>',
        reply_markup=keyboard.as_markup()
    )
    mg.new_game(
        [(player1, msg.from_user.full_name), (player2, msg.reply_to_message.from_user.full_name)],
        msg.chat.id, message.message_id
    )


@dp.message(Command('rules'))
async def rules(msg: types.Message):
    '''
    show game rules
    '''
    await msg.reply(mg.rules)


@dp.message(Command('leave'))
async def leave(msg: types.Message):
    '''
    leave an ongoing game.
    '''
    game = mg.get_game_playing(msg.from_user.id)

    # checking if not playing
    if not game:
        await msg.reply('ты не играешь!')
        return
    
    # keyboard
    await mg.end_game(game.id)

    await msg.reply('вы вышли из игры!')


# button answering

@dp.callback_query(F.data.startswith('accept:'))
async def accept(q: types.CallbackQuery):
    gameid = int(q.data.split(':')[1])
    id = int(q.data.split(':')[2])
    game = mg.get_game(gameid)

    if game == None:
        await q.answer('❌ не знаю такую игру')
        return

    if game.ready:
        await q.answer('❌ игра уже началась')
        return

    if q.from_user.id != id:
        await q.answer('❌ не для тебя моя кнопочка росла')
        return

    await q.answer('✅ игра начата')
    await game.ready_up()


@dp.callback_query(F.data.startswith('deny:'))
async def deny(q: types.CallbackQuery):
    gameid = int(q.data.split(':')[1])
    id = int(q.data.split(':')[2])
    game = mg.get_game(gameid)

    if game == None:
        await q.answer('❌ не знаю такую игру')
        return

    if game.ready:
        await q.answer('❌ игра уже началась')
        return

    if q.from_user.id not in [id, gameid]:
        await q.answer('❌ не для тебя моя кнопочка росла')
        return

    await q.answer('✅ игра отменена')
    await mg.end_game(game.id)



# answering inline query

@dp.chosen_inline_result()
async def inline_result(q: types.ChosenInlineResult):
    if q.result_id.startswith('discard'): return
    
    # ending game
    if q.result_id == 'cancel':
        game = mg.get_game_playing(q.from_user.id)
        
        if game:
            await mg.end_game(game.id)
    
    # choosing card
    if q.result_id.startswith('card:'):
        game = mg.get_game_playing(q.from_user.id)
        
        if game:
            card = int(q.result_id.split(':')[1])
            await game.use_card(q.from_user.id, card)
    
    # choosing card
    if q.result_id.startswith('typec:'):
        game = mg.get_game_playing(q.from_user.id)
        
        if game:
            card = q.result_id.split(':')[1]
            await game.answer_type_chooser(q.from_user.id, card)
    
    # taking card
    if q.result_id == 'take':
        game = mg.get_game_playing(q.from_user.id)
        
        if game:
            await game.take_card(q.from_user.id)
    
    # queen subbing
    if q.result_id == 'queen':
        game = mg.get_game_playing(q.from_user.id)
        
        if game:
            await game.queen_end(q.from_user.id)



# inline query

@dp.inline_query()
async def inline(q: types.InlineQuery):
    # checking game
    game = mg.get_game_playing(q.from_user.id)

    # no game
    if game is None:
        await q.answer([
            types.InlineQueryResultArticle(
                id='discard',
                title='ты сейчас не играешь!',
                input_message_content=types.InputTextMessageContent(
                    message_text='привет'
                )
            )
        ], cache_time=1, is_personal=True)
        return
    
    # waiting
    if game.waiting:
        await q.answer([
            types.InlineQueryResultArticle(
                id='discard',
                title='жди нового раунда!',
                input_message_content=types.InputTextMessageContent(
                    message_text='привет'
                )
            )
        ], cache_time=1, is_personal=True)
        return
    
    # waiting for opponent
    if not game.ready:
        await q.answer([
            types.InlineQueryResultArticle(
                id='cancel',
                title='оппонент не принял заявку!',
                description='❌ нажми чтобы покинуть игру',
                input_message_content=types.InputTextMessageContent(
                    message_text='лан не передумал'
                )
            )
        ], cache_time=1, is_personal=True)
        return
    
    # not your turn
    if q.from_user.id != game.turn:
        items = [
            types.InlineQueryResultArticle(
                id='cancel',
                title='сейчас не твой ход!',
                description='❌ нажми чтобы покинуть игру',
                input_message_content=types.InputTextMessageContent(
                    message_text='я слился'
                )
            )
        ]
        cards_list = game.players[q.from_user.id].cards
        cards = ' ・ '.join([str(i) for i in cards_list])
        items.append(types.InlineQueryResultArticle(
            id=f'discard',
            title=f'твои карты ({len(cards_list)})',
            description=cards,
            input_message_content=types.InputTextMessageContent(
                message_text=f'привет!'
            )
        ))

        await q.answer(items, cache_time=1, is_personal=True)
        return
    
    # card picker
    if game.type_chooser:
        items = []
        
        for i in config.TYPES:
            items.append(types.InlineQueryResultArticle(
                id=f'typec:{i}',
                title=f'{i} {config.NAMES[i]}',
                input_message_content=types.InputTextMessageContent(
                    message_text=f'{i} {config.NAMES[i]}'
                )
            ))

        cards_list = game.players[q.from_user.id].cards
        cards = ' ・ '.join([str(i) for i in cards_list])
        items.append(types.InlineQueryResultArticle(
            id=f'discard',
            title=f'твои карты ({len(cards_list)})',
            description=cards,
            input_message_content=types.InputTextMessageContent(
                message_text=f'привет!'
            )
        ))

        await q.answer(items, cache_time=1, is_personal=True)
        return
    
    # card picker
    if q.from_user.id == game.turn:
        items = [
            types.InlineQueryResultArticle(
                id='take',
                title='🔁 взять карту' if not game.took else '⏩ пропустить ход',
                input_message_content=types.InputTextMessageContent(
                    message_text='беру' if not game.took else 'пропускаю'
                )
            )
        ]

        if game.players[game.turn].is_queen_winnable:
            amount = sum([i.cost for i in game.players[game.turn].cards])
            items.append(types.InlineQueryResultArticle(
                id='queen',
                title=f'👑 списать дамами (-{amount})',
                input_message_content=types.InputTextMessageContent(
                    message_text='списываю!!'
                )
            ))
        
        for index, i in enumerate(game.players[game.turn].cards):
            if game.stack == None or i.is_hittable_on(game.stack):
                items.append(types.InlineQueryResultArticle(
                    id=f'card:{index}',
                    title=str(i),
                    input_message_content=types.InputTextMessageContent(
                        message_text=str(i)
                    )
                ))
            else:
                items.append(types.InlineQueryResultArticle(
                    id=f'discard{index}',
                    title="❌ "+str(i),
                    input_message_content=types.InputTextMessageContent(
                        message_text='этой картой играть нельзя!'
                    )
                ))

        await q.answer(items, cache_time=1, is_personal=True)
        return


# starting bot

print('Started polling...')
asyncio.run(dp.start_polling(bot))