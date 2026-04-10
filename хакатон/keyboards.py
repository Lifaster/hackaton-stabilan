from aiogram import types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

menuKeyboard = InlineKeyboardMarkup(inline_keyboard =[
    [InlineKeyboardButton(text = '⚖️Анализ стабилана⚖️', callback_data = 'stabilan')],
    [InlineKeyboardButton(text = '🦘Прыжки🦘', callback_data = 'jumps')]
])