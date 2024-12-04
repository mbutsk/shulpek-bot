
from typing import *

from aiogram import types, Dispatcher, Bot, F, client
from aiogram.filters.command import Command
import asyncio
from aiogram.utils.keyboard import InlineKeyboardBuilder

import os
from dotenv import load_dotenv

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

    await bot.edit_message_text(
        text = 'игра началась!',
        chat_id = game.chat,
        message_id = game.message
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

async def game_over(id: int):
    game = mg.get_game(id)
    if game == None: return

async def game_forfeited(id: int):
    game = mg.get_game(id)
    if game == None: return

async def request_deny(id: int):
    game = mg.get_game(id)
    if game == None: return


mg.hooks = engine.Hooks(
    game_start=game_start,
    card_used=card_used,
    round_over=round_over,
    game_over=game_over,
    game_forfeited=game_forfeited,
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
        await msg.reply(f'убери анонимность админов в настройках группы!')
        return

    if msg.reply_to_message.from_user.is_bot:
        await msg.reply(f'с ботом играть нельзя!')
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
        
    message = await msg.reply('бум', reply_markup=keyboard.as_markup())
    mg.new_game([player1, player2], msg.chat.id, message.message_id)


# button answering

@dp.callback_query(F.data.startswith('accept:'))
async def accept(q: types.CallbackQuery):
    gameid = int(q.data.split(':')[1])
    id = int(q.data.split(':')[2])
    game = mg.get_game_playing(gameid)

    if game == None:
        await q.answer('❌ не знаю такую игру')
        return

    if q.from_user.id != id:
        await q.answer('❌ не для тебя моя кнопочка росла')
        return

    await q.answer('✅')
    await game.ready_up()


@dp.callback_query(F.data.startswith('deny:'))
async def deny(q: types.CallbackQuery):
    gameid = int(q.data.split(':')[1])
    id = int(q.data.split(':')[2])
    game = mg.get_game_playing(gameid)

    if game == None:
        await q.answer('❌ не знаю такую игру')
        return

    if q.from_user.id not in [id, gameid]:
        await q.answer('❌ не для тебя моя кнопочка росла')
        return

    await q.answer('✅ игра отменена')
    await mg.end_game(game.id)



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
                title='вы сейчас не играете в игру!',
                input_message_content='привет'
            )
        ], cache_time=1)
        return


# starting bot

print('Started polling...')
asyncio.run(dp.start_polling(bot))