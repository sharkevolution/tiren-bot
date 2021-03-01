# -*- coding: UTF-8 -*-

# https://unicode.org/emoji/charts/full-emoji-list.html#1f600
# https://apps.timwhitlock.info/emoji/tables/unicode
# https://github.com/carpedm20/emoji/blob/master/emoji/unicode_codes.py
# https://habr.com/ru/company/ruvds/blog/325522/
# https://www.networkworld.com/article/3276349/copying-and-renaming-files-on-linux.html

import io
import os
import json
import copy
from datetime import datetime
from pytz import timezone

import bottle
from bottle import view, request, redirect

import requests
import logging
import redis
import msgpack
import emoji

from mybot.project.controllers import planner
from mybot.project.controllers import dredis
from mybot.project.controllers import settings_user
from mybot.project.controllers import chtime
from mybot.project.controllers import treeadr

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

PROD = {"url": "https://tiren-bot.herokuapp.com/api/v1/echo"}
TEST = {"url": "https://tirentest.herokuapp.com/api/v1/echo"}


def set_webhook(data, bottoken):
    headers = {'Content-type': 'application/json'}
    baseURL = f'https://api.telegram.org/bot{bottoken}/setWebhook'

    r = requests.get(baseURL, headers=headers, data=json.dumps(data))
    print(r.text)


def callback_hello_ok(data, text):
    try:
        #  "text": text, "cache_time": 0
        message = {"callback_query_id": data['callback_query']['id']}
        r = requests.post(bot.api_answer, data=json.dumps(message), headers=bot.headers)
        assert r.status_code == 200
    except Exception as ex:
        logging.error(ex)
    return r


def user_start_update(chat_id, _from):
    """ Start and Updater user profile """
    if not bot.users.get(chat_id):
        # Add info about User
        logging.info('Add info about User')
        clu = User(chat_id)
        clu.from_id = _from['id']

        clu.first_name = ''
        if _from.get('first_name'):
            clu.first_name = _from.get('first_name')

        clu.last_name = ''
        if _from.get('last_name'):
            clu.last_name = _from.get('last_name')

        clu.put_redis_info()
        bot.users[User(chat_id).__name__] = clu

    cs = bot.users[chat_id]
    csdata = cs.get_redis()
    if csdata.get('last_message_id'):
        cs.last_message_id = csdata['last_message_id']
    if csdata.get('from_id'):
        cs.from_id = csdata['from_id']
    if csdata.get('first_name'):
        cs.first_name = csdata['first_name']
    if csdata.get('last_name'):
        cs.last_name = csdata['last_name']

    bot.users[chat_id] = cs
    bot.last_chat = chat_id  # Active chat

    return cs


def handler_response_ok(resp):
    """ Обработчик успешного ответа от сервера """
    data = resp.json()
    if isinstance(data, dict):
        if data['result'] == True:
            pass
        elif data['result'].get('message_id'):
            mi = data['result'].get('message_id')
            # logging.info(data)
            chat_id = data['result']['chat']['id']
            cs = bot.users[chat_id]
            cs.put_redis_last_message_bot(mi)


class User:
    def __init__(self, chat_id):
        self.__name__ = chat_id
        self.from_id = None
        self.first_name = None
        self.last_name = None
        self.combination = []  # Time text value
        self.adr = []  # List of store addresses
        self.delivery = []  # List of carriers
        self.weight = []  # Capacity
        self.send_list = []  # Item delete from list to send

        self.gear_cities = []
        self.gear_adr = []

        self.bind_to_city = []

        self.last_message_id = 0
        self.last_bot_id = 0
        self.pull_user_commands = {}  # Add set user commands

        self.FSM = False
        self.call_fsm = None

        self.previous_ord = None
        self.fsm_location = [None, None]  # Address - City

        self.current_task = {}  # Current task
        self.redisClient = redis.from_url(os.environ.get("REDIS_URL"))

        self.selected_subscriber = 0
        self.selected_sub_data = {}
        self.selected_change_datetime = None

    def get_redis(self):

        res = {}
        if self.redisClient.exists(self.__name__):
            res = msgpack.unpackb(self.redisClient.get(self.__name__))
            # logging.info(res)
        return res

    def put_redis_last_message_id(self, data):

        self.last_message_id = data['message']['from']['id']
        if base_keys := self.get_redis():
            base_keys['last_message_id'] = self.last_message_id
        else:
            base_keys = {'last_message_id': self.last_message_id}
        new_pack = msgpack.packb(base_keys)
        self.redisClient.set(self.__name__, new_pack)

    def put_redis_last_message_bot(self, mi):

        self.last_bot_id = mi

        if base_keys := self.get_redis():
            base_keys['last_bot_id'] = self.last_bot_id
        else:
            base_keys = {'last_bot_id': self.last_bot_id}
        new_pack = msgpack.packb(base_keys)
        self.redisClient.set(self.__name__, new_pack)

    def put_redis_info(self):

        base_keys = {'from_id': self.from_id,
                     'first_name': self.first_name,
                     'last_name': self.last_name}
        new_pack = msgpack.packb(base_keys)
        self.redisClient.set(self.__name__, new_pack)

    def create_task(self):
        self.current_task = {'shop': None, 'delivery': None, 'weight': None,
                             'dlv_time': None, 'status_send': {str(self.__name__): 'pending'}
                             }

    def put_task(self):
        pass

    def __repr__(self):
        return self.__name__


class Bot:
    """ Bot token """

    def __init__(self, token):
        self.token = token
        self.api_url = f'https://api.telegram.org/bot{self.token}/sendMessage'
        self.api_answer = f'https://api.telegram.org/bot{self.token}/answerCallbackQuery'
        self.api_edit_message = f'https://api.telegram.org/bot{self.token}/editMessageText'
        self.api_get_updates = f'https://api.telegram.org/bot{self.token}/getUpdates'
        self.api_send_document = f'https://api.telegram.org/bot{self.token}/sendDocument'

        self.headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
        self.headers_multipart = {'Content-type': 'multipart/form-data'}

        self.users = {}  # List of users
        self.dict_init = {}  # Custom logic

        self.subscription = {}  # Messages from users who sent the message
        self.selected_subscriber = 0  #

        self.last_id = 0  # Last ID telegram (not message)
        self.last_chat = None  # Last chat
        self.tasks = {}  # Dict of users tasks

        self.admin_chat_id = 471125560  # Admin chat
        self.rdot = '.'
        self.rdot_three = '...'


class Dispatcher:
    """ handler messages command """

    def __init__(self, bot):
        self.bot = bot
        self.commands = None
        self.pull_message_commands = {}
        self.pull_callback_commands = {}

    def message_handler(self, commands):
        def decorator(fn):
            for b in commands:
                self.pull_message_commands[b] = fn

            def decorated2(*args, **kwargs):
                self.commands = commands
                return fn(*args, **kwargs)

            decorated2.__name__ = fn.__name__
            return decorated2

        return decorator

    def callback_handler(self, commands):
        def decorator(fn):
            for b in commands:
                self.pull_callback_commands[b] = fn

            def decorated2(*args, **kwargs):
                self.commands = commands
                return fn(*args, **kwargs)

            decorated2.__name__ = fn.__name__
            return decorated2

        return decorator


# ********************************************************
if API_TOKEN := os.environ.get("API_TOKEN"):
    logging.info(API_TOKEN)
else:
    logging.info('Not API_TOKEN')

bot = Bot(API_TOKEN)
dp = Dispatcher(bot)


# ********************************************************


@dp.message_handler(commands=['/tr', ])
def send_file(data, ord=None):
    if ord == '/tr':
        tunnel = data['message']['chat']['id']

    md = json.dumps(bot.dict_init)
    f = io.StringIO(md)
    f.name = 'tree.txt'
    post_file = {'document': f}

    message = {'chat_id': bot.admin_chat_id, 'caption': 'Дерево связей'}

    # Admin chat
    curl = bot.api_send_document
    try:
        r = requests.post(curl, data=message, files=post_file)
        assert r.status_code == 200
        logging.info(r.content)

    except Exception as ex:
        logging.info(str(r))
        logging.error('Error' + str(ex))

    return {}, {}


def insert_seal(data, ord=None):
    """ FSM add Insert Seal """
    tunnel = data['message']['chat']['id']
    chat_user = bot.users[tunnel]

    result_text = f"Добавлен номер пломбы"

    single_quote = '\''
    seal = f'Пломба: {ord[3:].strip()}'
    seal_number = "".join([bot.rdot_three, ' ', single_quote, seal, single_quote])

    if tmp_ := bot.tasks.get(tunnel):
        tmp_[seal_number] = seal_number
        bot.tasks[tunnel] = tmp_
        logging.info('ADD Seal number')
        logging.info(bot.tasks)
    else:
        bot.tasks[tunnel] = {seal_number: seal_number}
        logging.info(bot.tasks)

    res = {'chat_id': tunnel, 'text': result_text}
    return res, bot.api_url


def fsm_city(data, ord=None):
    """ FSM add new city """
    tunnel = data['message']['chat']['id']
    chat_user = bot.users[tunnel]

    result_text = f"Несоздана связь есть дубли"
    logging.info(chat_user.previous_ord)
    if chat_user.previous_ord == 'add_city':
        chat_user.FSM = False
        chat_user.previous_ord = None
        chat_user.call_fsm = None

        # Check City in list and save to Redis
        single_quote = '\''
        new_city_split = ord.split(f"{single_quote}")
        if len(new_city_split) > 1:
            idx = 1
        else:
            idx = 0

        chat_user.fsm_location[1] = new_city_split[idx]

        dup_city = True
        dup_adr = True

        city_ = sorted(bot.dict_init['city'], key=lambda num: int(num[0]), reverse=True)
        max_key_city = city_[0][0]  # New key

        for b in bot.dict_init['city']:
            if new_city_split[idx].lower() == b[1].lower():
                logging.info(new_city_split[idx].lower())
                dup_city = False
                logging.info("dup_city = false")
                max_key_city = b[0]
                break

        # Check Address in list and save to Redis
        adr_ = sorted(bot.dict_init['adr'], key=lambda num: int(num[1]), reverse=True)
        max_key_address = adr_[0][1]  # New key
        # new_adr = chat_user.fsm_location[0]

        new_adr = ', '.join([new_city_split[idx], chat_user.fsm_location[0]])  # Append City name to address

        for b in bot.dict_init['adr']:
            if new_adr.lower() == b[2].lower():
                dup_adr = False
                break

        # Add to Redis
        if dup_adr:
            logging.info(chat_user.fsm_location)
            link = '-'.join(chat_user.fsm_location)
            if dup_city:
                result_text = f"Добавлен новый адрес и создан новый город: {link}"
                # New City
                max_key_city = int(max_key_city) + 1
                city_.append([str(max_key_city), new_city_split[idx], []])
                rev_city = sorted(city_, key=lambda num: int(num[0]), reverse=True)
                bot.dict_init['city'] = rev_city
            else:
                # City exists
                result_text = f"Добавлен новый адрес и привязан к существующему городу: {link}"
                pass

            max_key_address = int(max_key_address) + 1
            adr_.append([str(max_key_city), str(max_key_address), new_adr, []])
            rev_adr = sorted(adr_, key=lambda num: num[1], reverse=True)
            bot.dict_init['adr'] = rev_adr

            dredis.save_variable(bot.dict_init)
            # logging.info(dredis.read_variable())

    else:
        logging.info("bad FSM")
        chat_user.FSM = False
        chat_user.previous_ord = None
        chat_user.call_fsm = None
        chat_user.fsm_location = [None, None, None]
        bot.users[tunnel] = chat_user

        return {}, {}

    bot.users[tunnel] = chat_user
    chat_user.fsm_location = [None, None]

    res = {'chat_id': tunnel, 'text': result_text}
    return res, bot.api_url


def fsm_address(data, ord=None):
    """ FSM add new address """
    logging.info("I'm fsm_address")

    tunnel = data['message']['chat']['id']
    chat_user = bot.users[tunnel]

    if chat_user.previous_ord == 'add_address':
        chat_user.FSM = True
        chat_user.previous_ord = 'add_city'
        chat_user.call_fsm = fsm_city
        chat_user.fsm_location[0] = ord
    else:
        logging.info("bad FSM")
        chat_user.FSM = False
        chat_user.previous_ord = None
        chat_user.call_fsm = None
        chat_user.fsm_location = [None, None]
        bot.users[tunnel] = chat_user

        return {}, {}

    bot.users[tunnel] = chat_user

    result_text = f"Привяжите к городу из списка или введите новый.."
    reply_markup, chat_user = settings_user.template_fsm_city(bot.dict_init, chat_user)
    # Update commands wrapper
    for b in chat_user.bind_to_city[:-1]:
        chat_user.pull_user_commands[b] = fsm_city

    # event TOP
    back = chat_user.bind_to_city[-1]
    logging.info(back)
    chat_user.pull_user_commands[back] = start_bot

    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}
    return message, bot.api_url


@dp.message_handler(commands=[])
def gear_del_handler_adr(data, ord=None):
    tunnel = data['message']['chat']['id']
    nDict = dredis.read_variable()
    bot.dict_init = nDict
    tree_ = treeadr.delete_address(bot.dict_init['adr'], tunnel, ord)
    bot.dict_init['adr'] = tree_
    dredis.save_variable(bot.dict_init)

    logging.info(tree_)

    reply_markup, chat_user = settings_user.template_gear_del_address(bot.dict_init, bot.users[tunnel])

    # Update commands wrapper
    for b in chat_user.gear_adr[:-1]:
        chat_user.pull_user_commands[b] = gear_del_handler_adr

    # event TOP
    back = chat_user.gear_adr[-1]
    logging.info('gear_del_handler_city')
    logging.info(back)
    chat_user.pull_user_commands[back] = start_bot

    bot.users[tunnel] = chat_user

    result_text = f"Полностью {ord}"
    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    return message, bot.api_url


@dp.callback_handler(commands=["gear_del_address", ])
def gear_del_addess_user(data, ord=None):
    callback_hello_ok(data, 'ok')

    tunnel = data['callback_query']['message']['chat']['id']
    result_text = 'Удалить адрес из базы у Всех пользователей, без возможности Восстановления'
    reply_markup, chat_user = settings_user.template_gear_del_address(bot.dict_init, bot.users[tunnel])

    # Update commands wrapper
    for b in chat_user.gear_adr[:-1]:
        chat_user.pull_user_commands[b] = gear_del_handler_adr

    # event TOP
    back = chat_user.gear_adr[-1]
    logging.info('gear_add_city_user')
    logging.info(back)
    chat_user.pull_user_commands[back] = start_bot

    # Control delete address
    send_file(data, ord=None)

    bot.users[tunnel] = chat_user
    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    return message, bot.api_url


@dp.message_handler(commands=[])
def gear_del_handler_city(data, ord=None):
    tunnel = data['message']['chat']['id']
    nDict = dredis.read_variable()
    bot.dict_init = nDict
    tree_ = treeadr.hide_city(bot.dict_init['city'], tunnel, ord)
    bot.dict_init['city'] = tree_
    dredis.save_variable(bot.dict_init)

    logging.info(tree_)

    reply_markup, chat_user = settings_user.template_gear_del_city(bot.dict_init, bot.users[tunnel])

    # Update commands wrapper
    for b in chat_user.gear_cities[:-1]:
        chat_user.pull_user_commands[b] = gear_del_handler_city

    # event TOP
    back = chat_user.gear_cities[-1]
    logging.info('gear_del_handler_city')
    logging.info(back)
    chat_user.pull_user_commands[back] = start_bot

    bot.users[tunnel] = chat_user

    result_text = f"{ord}"
    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    return message, bot.api_url


@dp.callback_handler(commands=["gear_del_city", ])
def gear_del_city_user(data, ord=None):
    callback_hello_ok(data, 'ok')

    tunnel = data['callback_query']['message']['chat']['id']
    result_text = 'Удалите город из своего списка'
    reply_markup, chat_user = settings_user.template_gear_del_city(bot.dict_init, bot.users[tunnel])

    # Update commands wrapper
    for b in chat_user.gear_cities[:-1]:
        chat_user.pull_user_commands[b] = gear_del_handler_city

    # event TOP
    back = chat_user.gear_cities[-1]
    logging.info('gear_add_city_user')
    logging.info(back)
    chat_user.pull_user_commands[back] = start_bot

    bot.users[tunnel] = chat_user

    # logging.info('Region arrived')
    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    return message, bot.api_url


@dp.message_handler(commands=[])
def gear_add_handler_city(data, ord=None):
    tunnel = data['message']['chat']['id']
    nDict = dredis.read_variable()
    bot.dict_init = nDict
    tree_ = treeadr.show_city(bot.dict_init['city'], tunnel, ord)
    bot.dict_init['city'] = tree_
    dredis.save_variable(bot.dict_init)

    logging.info(tree_)

    reply_markup, chat_user = settings_user.template_gear_add_city(bot.dict_init, bot.users[tunnel])

    # Update commands wrapper
    for b in chat_user.gear_cities[:-1]:
        chat_user.pull_user_commands[b] = gear_add_handler_city

    # event TOP
    back = chat_user.gear_cities[-1]
    logging.info('gear_add_handler_city')
    logging.info(back)
    chat_user.pull_user_commands[back] = start_bot

    bot.users[tunnel] = chat_user

    result_text = f"{ord}"
    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    return message, bot.api_url


def gear_insert_new_city(data, ord=None):
    callback_hello_ok(data, 'ok')
    tunnel = data['callback_query']['message']['chat']['id']
    result_text = 'Введите название нового города в строку для ввода текста'

    logging.info('New City enter')
    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    return message, bot.api_url


@dp.callback_handler(commands=["gear_add_city", ])
def gear_add_city_user(data, ord=None):
    callback_hello_ok(data, 'ok')

    tunnel = data['callback_query']['message']['chat']['id']
    result_text = 'Добавьте город в свой список'
    reply_markup, chat_user = settings_user.template_gear_add_city(bot.dict_init, bot.users[tunnel])

    # Update commands wrapper
    for b in chat_user.gear_cities[:-1]:
        chat_user.pull_user_commands[b] = gear_add_handler_city

    # event TOP
    back = chat_user.gear_cities[-1]
    logging.info('gear_add_city_user')
    logging.info(back)
    chat_user.pull_user_commands[back] = start_bot

    bot.users[tunnel] = chat_user

    # logging.info('Region arrived')
    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    return message, bot.api_url


@dp.callback_handler(commands=["gear_view", ])
def gear_view_user(data, ord=None):
    callback_hello_ok(data, 'ok')
    return {}, {}


@dp.callback_handler(commands=["gear", ])
def gear_user(data, ord=None):
    callback_hello_ok(data, 'ok')

    tunnel = data['callback_query']['message']['chat']['id']
    result_text = f"Настройки пользователя"
    reply_markup = settings_user.template_gear()
    logging.info(reply_markup)
    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    return message, bot.api_url


@dp.callback_handler(commands=['add_address', ])
def enter_add_address(data, ord=None):
    callback_hello_ok(data, 'add_address')

    tunnel = data['callback_query']['message']['chat']['id']
    chat_user = bot.users[tunnel]

    chat_user.FSM = True
    chat_user.previous_ord = 'add_address'  # Save previous ord for FSM
    chat_user.call_fsm = fsm_address  # Call name function
    bot.users[tunnel] = chat_user

    result_text = f"Введите новый адрес без названия города и нажимте отправить.."
    # reply_markup = settings_user.template_fsm_address()
    reply_markup = settings_user.template_remove_keboard()
    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    return message, bot.api_url


@dp.callback_handler(commands=['ent_send', ])
def enter_to_send(data, ord=None):
    logging.info('enter_to_send')
    callback_hello_ok(data, 'Send data for aggregate')

    tunnel = data['callback_query']['message']['chat']['id']
    chat_user = bot.users[tunnel]

    kiev = timezone('Europe/Kiev')
    now = datetime.now(kiev)
    date_time = now.strftime("%m/%d/%Y, %H:%M:%S")

    if bot.tasks.get(chat_user.from_id):
        crt = dict(bot.tasks[chat_user.from_id])

        if agr := bot.subscription.get(str(chat_user.from_id)):
            agr.append((date_time, crt))
            bot.subscription[str(chat_user.from_id)] = agr
        else:
            logging.info('new subscribe')
            bot.subscription[str(chat_user.from_id)] = [[date_time, crt]]

        # logging.info(bot.subscription)
        dredis.save_subscription(bot.subscription)  # save to Redis
        # logging.info(dredis.read_subscription())

    # logging.info('bot subscr')

    result_text = "Список доступен для консолидации и автоматически будет удален через 24 часа"
    reply_markup = settings_user.template_start()
    message = {'chat_id': tunnel, 'text': result_text}
    return message, bot.api_url


@dp.callback_handler(commands=['ent_main', ])
def enter_top(data, ord=None):
    callback_hello_ok(data, 'Jump to TOP')

    tunnel = data['callback_query']['message']['chat']['id']

    chat_user = bot.users[tunnel]
    chat_user.create_task()  # Create task
    bot.users[tunnel] = chat_user

    reply_markup = settings_user.template_remove_keboard()
    message = {'chat_id': tunnel, 'text': 'Переход на главную', 'reply_markup': reply_markup}

    r = requests.post(bot.api_url, data=json.dumps(message), headers=bot.headers)
    assert r.status_code == 200

    result_text = f"Hi {emoji.emojize(':waving_hand:')} .Коммент можно написать через точку, " \
                  f"номер пломбы можно записать через троеточие ...123456"
    reply_markup = settings_user.template_start()
    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}
    return message, bot.api_url


@dp.message_handler(commands=[])
def back_to_shop(data, ord=None):
    tunnel = data['message']['chat']['id']
    result_text = 'Выберите адрес из списка'
    reply_markup, chat_user = settings_user.template_shops(bot.dict_init, bot.users[tunnel])

    logging.info('TOP')
    # Update commands wrapper
    for b in chat_user.adr[:-1]:
        chat_user.pull_user_commands[b] = dynamic_delivery

    # event Shop
    back = chat_user.adr[-1]
    logging.info('Shops')
    logging.info(back)
    chat_user.pull_user_commands[back] = start_bot

    chat_user.create_task()  # Create task
    bot.users[tunnel] = chat_user

    logging.info('Region arrived')
    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    return message, bot.api_url


@dp.message_handler(commands=[])
def dynamic_weight(data, ord=None):
    logging.info('Weight')
    tunnel = data['message']['chat']['id']
    result_text = 'Грузоподъемность'
    reply_markup, chat_user = settings_user.template_weight(bot.dict_init, bot.users[tunnel])

    # Update commands wrapper
    for b in chat_user.weight[:-1]:
        chat_user.pull_user_commands[b] = keboard_bot

    # event Back
    back = chat_user.weight[-1]
    chat_user.pull_user_commands[back] = dynamic_delivery

    logging.info(ord)
    if not 'Назад' in ord:
        chat_user.current_task['delivery'] = ord
    bot.users[tunnel] = chat_user

    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}
    return message, bot.api_url


@dp.message_handler(commands=[])
def dynamic_delivery(data, ord=None):
    logging.info('Delivery')
    logging.info(ord)
    tunnel = data['message']['chat']['id']

    result_text = 'Выберите перевозчика'
    reply_markup, chat_user = settings_user.template_delivery(bot.dict_init, bot.users[tunnel])

    # Update commands wrapper
    for b in chat_user.delivery[:-1]:
        chat_user.pull_user_commands[b] = dynamic_weight

    # event back
    back = chat_user.delivery[-1]
    chat_user.pull_user_commands[back] = back_to_shop

    logging.info(ord)
    if not 'Назад' in ord:
        chat_user.current_task['shop'] = ord
    bot.users[tunnel] = chat_user

    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}
    return message, bot.api_url


@dp.message_handler(commands=[])
def consolidate(data, ord):
    logging.info('Consolidate')
    logging.info(ord)

    tunnel = data['message']['chat']['id']
    chat_user = bot.users[tunnel]
    result_text = f'{ord}'

    if ord == 'Принять':

        result_text = 'Данные добавлены в личный список'
        if tmp_dict := bot.tasks.get(tunnel):

            # Найти элементы subscription и изменить статус на добавлено
            settings_user.change_status_subscription(bot, chat_user, status='combined')
            dredis.save_subscription(bot.subscription)

            logging.info(tmp_dict)
            logging.info('------------------------')
            logging.info(chat_user.selected_sub_data)

            new_tmp = {**tmp_dict, **chat_user.selected_sub_data}

            logging.info('************************')
            logging.info(new_tmp)

            bot.tasks[tunnel] = new_tmp
        else:

            settings_user.change_status_subscription(bot, chat_user, status='combined')
            dredis.save_subscription(bot.subscription)
            bot.tasks[tunnel] = {**chat_user.selected_sub_data}

    message = {'chat_id': tunnel, 'text': result_text}

    return message, bot.api_url


@dp.message_handler(commands=[])
def reject_sub_data(data, ord):
    logging.info('Reject')
    logging.info(ord)

    tunnel = data['message']['chat']['id']
    chat_user = bot.users[tunnel]
    result_text = f'{ord}'

    if ord == 'Отклонить':
        result_text = 'Данные отмечены как нежелательные'
        if tmp_dict := bot.tasks.get(tunnel):

            # Найти элементы subscription и изменить статус на добавлено
            settings_user.change_status_subscription(bot, chat_user, status='rejected')
            dredis.save_subscription(bot.subscription)

        else:
            settings_user.change_status_subscription(bot, chat_user, status='rejected')
            dredis.save_subscription(bot.subscription)

            # bot.tasks[tunnel] = {}
            # bot.tasks[tunnel] = chat_user.selected_sub_data

    message = {'chat_id': tunnel, 'text': result_text}

    return message, bot.api_url


@dp.message_handler(commands=[])
def back_sub_users(data, ord=None):
    tunnel = data['message']['chat']['id']
    chat_user = bot.users[tunnel]
    result_text = 'Просмотрите сообщения пользователей перед консолидацией'

    reply_markup, commands_ = settings_user.template_subscription(bot)

    # Update commands wrapper
    for b in commands_[:-1]:
        chat_user.pull_user_commands[b] = dynamic_sub_users

    # event TOP
    back = commands_[-1]
    logging.info('TOP')
    logging.info(back)
    chat_user.pull_user_commands[back] = start_bot

    bot.users[tunnel] = chat_user

    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    return message, bot.api_url


@dp.message_handler(commands=[])
def back_sub_data(data, ord=None):
    logging.info('back to subscriptions detail')
    tunnel = data['message']['chat']['id']
    chat_user = bot.users[tunnel]

    for b in bot.subscription:
        if b == chat_user.selected_subscriber:
            if me := bot.users.get(int(b)):
                ord = ' '.join([me.first_name, me.last_name, b])
                break

    result_text = f'Выберите сообщение от {ord}'
    reply_markup, commands_ = settings_user.template_sub_datetime(bot, chat_user, ord)

    for b in commands_[:-2]:  # Update commands wrapper
        chat_user.pull_user_commands[b] = dynamic_sub_data

    back = commands_[-2]  # функция обработки нажатия К именам
    chat_user.pull_user_commands[back] = back_sub_users

    back = commands_[-1]  # event TOP
    chat_user.pull_user_commands[back] = start_bot

    bot.users[tunnel] = chat_user
    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    return message, bot.api_url


@dp.message_handler(commands=[])
def dynamic_sub_data(data, ord=None):
    logging.info('List of subscriptions detail')
    logging.info(ord)
    tunnel = data['message']['chat']['id']
    chat_user = bot.users[tunnel]

    chat_user.selected_change_datetime = ord  # User select datetime
    reply_markup, commands_, result_text = settings_user.template_sub_print(bot, chat_user, ord)

    chat_user.pull_user_commands[commands_[0]] = consolidate  # функция обработки нажатия принять
    chat_user.pull_user_commands[commands_[1]] = reject_sub_data  # функция обработки нажатия Отклонить
    chat_user.pull_user_commands[commands_[2]] = back_sub_data  # функция обработки нажатия К датам
    chat_user.pull_user_commands[commands_[3]] = back_sub_users  # функция обработки нажатия К именам

    # event TOP
    back = commands_[-1]
    logging.info('TOP')
    logging.info(back)
    chat_user.pull_user_commands[back] = start_bot

    bot.users[tunnel] = chat_user
    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    return message, bot.api_url


@dp.message_handler(commands=[])
def dynamic_sub_users(data, ord=None):
    logging.info('List of subscriptions users')
    tunnel = data['message']['chat']['id']
    chat_user = bot.users[tunnel]

    result_text = f'Выберите сообщение от {ord}'
    reply_markup, commands_ = settings_user.template_sub_datetime(bot, chat_user, ord)

    # Update commands wrapper
    for b in commands_[:-2]:
        chat_user.pull_user_commands[b] = dynamic_sub_data

    back = commands_[-2]
    chat_user.pull_user_commands[back] = back_sub_users  # функция обработки нажатия К именам

    # event TOP
    back = commands_[-1]
    logging.info('TOP')
    logging.info(back)
    chat_user.pull_user_commands[back] = start_bot

    bot.users[tunnel] = chat_user

    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}
    return message, bot.api_url


@dp.callback_handler(commands=['aggregate', ])
def dynamic_aggregate(data, ord=None):
    callback_hello_ok(data, 'Aggregate')

    tunnel = data['callback_query']['message']['chat']['id']
    chat_user = bot.users[tunnel]
    result_text = 'Просмотрите сообщения пользователей перед консолидацией'

    reply_markup, commands_ = settings_user.template_subscription(bot)

    # Update commands wrapper
    for b in commands_[:-1]:
        chat_user.pull_user_commands[b] = dynamic_sub_users

    # event TOP
    back = commands_[-1]
    logging.info('TOP')
    logging.info(back)
    chat_user.pull_user_commands[back] = start_bot

    bot.users[tunnel] = chat_user

    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    return message, bot.api_url


@dp.callback_handler(commands=['region_arrived', ])
def dynamic_shops(data, ord=None):
    callback_hello_ok(data, 'Переход на время прибытия')

    tunnel = data['callback_query']['message']['chat']['id']
    result_text = 'Выберите адрес из списка'
    reply_markup, chat_user = settings_user.template_shops(bot.dict_init, bot.users[tunnel])

    # Update commands wrapper
    for b in chat_user.adr[:-1]:
        chat_user.pull_user_commands[b] = dynamic_delivery

    # event TOP
    back = chat_user.adr[-1]
    logging.info('TOP')
    logging.info(back)
    chat_user.pull_user_commands[back] = start_bot

    chat_user.create_task()  # Create task
    bot.users[tunnel] = chat_user

    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    return message, bot.api_url


@dp.message_handler(commands=[])
def delete_item_send(data, ord=None):
    logging.info('delete_item_send')
    tunnel = data['message']['chat']['id']

    # Remove item list, dict and Update
    chat_user = bot.users[tunnel]
    if ord in chat_user.send_list:
        _tmp = bot.tasks[tunnel]

        if tmp_dict := bot.tasks.get(tunnel):
            if ord in tmp_dict:

                # Очистка данных для консолидации от других пользов
                chat_user.selected_subscriber = 0
                chat_user.selected_sub_data = {}

                logging.info(ord)
                tmp_dict.pop(ord)  # delete item from dict
                bot.tasks[tunnel] = tmp_dict
                chat_user.send_list.remove(ord)  # Delete item from list
                bot.users[tunnel] = chat_user
            else:
                logging.info('not found ord')
                logging.info(tmp_dict)

    _tmp = bot.tasks[tunnel]
    reply_markup, chat_user = settings_user.template_tasks_to_send(_tmp, bot.users[tunnel], bot.rdot)

    kb = reply_markup['keyboard']

    if kb:
        logging.info(reply_markup)
        message = {'chat_id': tunnel, 'text': f"{emoji.emojize(':skull_and_crossbones:')}: {ord}",
                   'reply_markup': reply_markup}
    else:
        # Goto Start bot
        result_text = f"Список пуст {emoji.emojize(':eyes:')}"
        reply_markup = settings_user.template_remove_keboard()
        message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

        r = requests.post(bot.api_url, data=json.dumps(message), headers=bot.headers)
        assert r.status_code == 200

        result_text = f"Hi {emoji.emojize(':waving_hand:')}"
        reply_markup = settings_user.template_start()
        message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    return message, bot.api_url


@dp.callback_handler(commands=['del_list_send'])
def delete_send(data, ord=None):
    """
        Remove list to send
    """
    r = callback_hello_ok(data, 'ok!')
    tunnel = data['callback_query']['message']['chat']['id']

    # Remove item list, dict and Update
    chat_user = bot.users[tunnel]

    if bot.tasks.get(tunnel):
        del bot.tasks[tunnel]
        chat_user.send_list = []
        bot.users[tunnel] = chat_user

        # Очистка данных для консолидации от других пользов
        chat_user.selected_subscriber = 0
        chat_user.selected_sub_data = {}

    else:
        logging.info('not found')

    # Goto Start bot
    result_text = f"Список пуст {emoji.emojize(':eyes:')}"
    reply_markup = settings_user.template_remove_keboard()
    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    r = requests.post(bot.api_url, data=json.dumps(message), headers=bot.headers)
    assert r.status_code == 200

    result_text = f"Hi {emoji.emojize(':waving_hand:')}"
    reply_markup = settings_user.template_start()
    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    return message, bot.api_url


@dp.callback_handler(commands=['edit_list_send'])
def edit_send(data, ord=None):
    """
        Remove an item from the list to send
    """
    r = callback_hello_ok(data, 'ok!')
    chat_id = data['callback_query']['message']['chat']['id']

    # _tmp = bot.tasks[chat_id]
    # logging.info('Add to sd list ******************')
    # logging.info(_tmp)

    reply_markup, chat_user = settings_user.template_tasks_to_send(bot.tasks[chat_id],
                                                                   bot.users[chat_id],
                                                                   bot.rdot)

    logging.info(chat_user.send_list)

    for b in chat_user.send_list:
        chat_user.pull_user_commands[b] = delete_item_send

    message = {'chat_id': chat_id, 'text': f'Выбранный элемент будет удален', 'reply_markup': reply_markup}

    return message, bot.api_url


@dp.callback_handler(commands=['ent_list'])
def enter_to_list(data, ord=None):
    r = callback_hello_ok(data, 'ok!')
    chat_id = data['callback_query']['message']['chat']['id']

    if tmp_dict := bot.tasks.get(chat_id):

        me = bot.users.get(chat_id)
        me_first = me.first_name
        me_last = me.last_name

        single_quote = '\''
        html_list = []  # view for screen user
        for ts in tmp_dict:
            cnt = tmp_dict[ts]
            if bot.rdot in ts[0:1]:
                html_list.append(cnt)
            else:
                # cnt = tmp_dict[ts]
                qsh = single_quote + cnt['shop'] + single_quote
                tmp_text = ', '.join([qsh, cnt['delivery'], cnt['weight'], cnt['dlv_time'], ])
                html_list.append(tmp_text)

        html_list.insert(0, ' '.join([me_first, me_last]))
        result_text = '\n'.join(html_list)

        # Button remove from list
        reply_markup = settings_user.template_edit_list()

        res = {'chat_id': chat_id, 'text': result_text, 'parse_mode': 'HTML',
               'reply_markup': reply_markup}

    else:
        result_text = f"Список пуст {emoji.emojize(':eyes:')}"
        res = {'chat_id': chat_id, 'text': result_text, }

    logging.info(res)
    return res, bot.api_url


@dp.callback_handler(commands=['ent_shops'])
def return_to_shops(data, ord=None):
    r = callback_hello_ok(data, 'ok!')
    tunnel = data['callback_query']['message']['chat']['id']
    chat_user = bot.users[tunnel]

    result_text = 'Выберите адрес из списка'
    logging.info('Return to SHOPS')
    logging.info(chat_user)

    reply_markup, chat_user = settings_user.template_shops(bot.dict_init, bot.users[tunnel])

    # Update commands wrapper
    for b in chat_user.adr[-1]:
        chat_user.pull_user_commands[b] = dynamic_delivery

    # event Shop
    back = chat_user.adr[-1]
    logging.info('Return to shops')
    logging.info(back)
    chat_user.pull_user_commands[back] = start_bot

    # Create task
    chat_user.create_task()
    bot.users[tunnel] = chat_user
    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    return message, bot.api_url


@dp.callback_handler(commands=['ent_backspace', ])
def enter_backspase(data, ord=None):
    r = callback_hello_ok(data, 'ok!')
    chat_id = data['callback_query']['message']['chat']['id']

    chat_user = bot.users[chat_id]
    # Backspace Message

    crs = copy.deepcopy(chat_user.current_task)
    logging.info(crs)
    if not crs['dlv_time'] is None:
        nm = ', '.join([crs['shop'], crs['delivery'], crs['weight'], crs['dlv_time'], ])

        if tmp_ := bot.tasks.get(chat_id):
            if tmp_.get(nm):
                del tmp_[nm]

    chat_user.current_task['dlv_time'] = None

    if not chat_user.combination:
        return {}, {}

    if len(chat_user.combination) > 3:
        my_test = ''.join(chat_user.combination[:3])
        chat_user.combination = chat_user.combination[:3]
    else:
        my_test = 'Your time:'
        chat_user.combination = []

    base_keys = chat_user.get_redis()
    chat_user.last_message_id = base_keys['last_bot_id']

    curl = bot.api_edit_message
    message = {'chat_id': chat_id, 'message_id': chat_user.last_message_id, 'text': my_test}

    logging.info('EDIT Message')
    logging.info(chat_user.last_message_id)

    try:
        r = requests.post(curl, data=json.dumps(message), headers=bot.headers)
        assert r.status_code == 200

        handler_response_ok(r)  # Обработчик ответа

    except Exception as ex:
        logging.info(r)
        logging.error('Error' + str(ex))

    return {}, {}


@dp.callback_handler(commands=['ent_one', 'ent_two', 'ent_three', 'ent_four', 'ent_five',
                               'ent_six', 'ent_seven', 'ent_eight', 'ent_nine', 'ent_zero',
                               'ent_colon'])
def enter(data, ord=None):
    r = callback_hello_ok(data, 'ok!')
    chat_id = data['callback_query']['message']['chat']['id']

    chat_user = bot.users[chat_id]
    # Edit Message
    check_list = chtime.check(ord, chat_user.combination)

    my_test = ''.join(check_list)
    my_comb = ''.join(chat_user.combination)

    if my_test == my_comb:

        return {}, {}

    else:
        chat_user.combination = check_list
        if len(chat_user.combination) == 5:
            chat_user.current_task['dlv_time'] = my_test
            logging.info(chat_user.current_task)

            val = 0
            for b in chat_user.current_task:
                if not chat_user.current_task[b] is None:
                    val += 1
            if val == 5:
                # Add tasks to the dict from send
                crs = copy.deepcopy(chat_user.current_task)

                # Join name
                nm = ', '.join([crs['shop'], crs['delivery'], crs['weight'], crs['dlv_time'], ])

                if tmp_ := bot.tasks.get(chat_id):
                    tmp_[nm] = crs
                    bot.tasks[chat_id] = tmp_
                    logging.info('ADD')
                    logging.info(bot.tasks)
                else:
                    bot.tasks[chat_id] = {nm: crs}
                    logging.info(bot.tasks)
                    # bot.tasks[chat_id] = [crs, ]
                    # logging.info(bot.tasks)

    base_keys = chat_user.get_redis()
    chat_user.last_message_id = base_keys['last_bot_id']

    curl = bot.api_edit_message
    message = {'chat_id': chat_id, 'message_id': chat_user.last_message_id, 'text': my_test}

    logging.info('EDIT Message')
    logging.info(chat_user.last_message_id)

    try:
        r = requests.post(curl, data=json.dumps(message), headers=bot.headers)
        assert r.status_code == 200

        handler_response_ok(r)  # Обработчик ответа

    except Exception as ex:
        logging.info(r)
        logging.error('Error' + str(ex))

    return {}, {}


def comment_additional(data, ord=None):
    tunnel = data['message']['chat']['id']

    single_quote = '\''
    comment = ord[1:].strip()
    comment = "".join([bot.rdot, ' ', single_quote, comment, single_quote])

    if tmp_ := bot.tasks.get(tunnel):
        tmp_[comment] = comment
        bot.tasks[tunnel] = tmp_
        logging.info('ADD comment')
        logging.info(bot.tasks)
    else:
        bot.tasks[tunnel] = {comment: comment}
        logging.info(bot.tasks)

    message = {'chat_id': tunnel, 'text': f'Добавлен коммент: {ord}'}
    return message, bot.api_url


@dp.message_handler(commands=['/clear_base', ])
def clear_redis_base(data, ord=None):
    dredis.clear_base_redis()

    bot.users = {}  # Reset users

    tunnel = data['message']['chat']['id']
    message = {'chat_id': tunnel, 'text': 'Clear base Redis is ok!'}
    return message, bot.api_url


@dp.message_handler(commands=['/chat', ])
def bind_bot(data, ord=None):
    tunnel = data['message']['chat']['id']
    message = {'chat_id': tunnel, 'text': data['message']['chat']['id']}
    return message, bot.api_url


@dp.message_handler(commands=['/bc', ])
def keboard_bot(data, ord=None):
    tunnel = data['message']['chat']['id']
    result_text = 'Введите время прибытия'
    reply_markup = settings_user.template_engineer_mode()
    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}

    r = requests.post(bot.api_url, data=json.dumps(message), headers=bot.headers)
    assert r.status_code == 200

    chat_user = bot.users[tunnel]
    chat_user.current_task['weight'] = ord

    # Input pass
    chat_user.combination = []
    bot.users[tunnel] = chat_user

    result_text = "Your time: "
    message = {'chat_id': data['message']['chat']['id'], 'text': result_text}

    try:
        r = requests.post(bot.api_url, data=json.dumps(message), headers=bot.headers)
        assert r.status_code == 200
        handler_response_ok(r)  # Ловушка для получения ид сообщения от бота

    except Exception as ex:
        logging.info(r)
        logging.error('Error' + str(ex))

    return {}, {}


@dp.message_handler(commands=['/start', ])
def start_bot(data, ord=None):
    tunnel = data['message']['chat']['id']
    result_text = f"Hi {emoji.emojize(':waving_hand:')} .Коммент можно написать через точку" \
                  f"номер пломбы можно записать через троеточие ...123456"
    reply_markup = settings_user.template_start()
    message = {'chat_id': tunnel, 'text': result_text, 'reply_markup': reply_markup}
    return message, bot.api_url


def dummy_message(data):
    """ Заглушка для message """
    text = data['message'].get('text')
    result_text = f"Функция [{text}] в разработке."
    res = {'chat_id': data['message']['chat']['id'], 'text': result_text}
    return res, bot.api_url


def dummy_callback(data):
    """ Заглушка для callback_query """

    planner.start_proc()  # Run planner in different process
    logging.info("I am!")

    text = data['callback_query']['data']
    result_text = f"Функция [ {text} ] в разработке."
    res = {"callback_query_id": data['callback_query']['id'], "text": result_text, "cache_time": 3}
    return res, bot.api_answer


def reload_bot(data):
    """ Перезагрузка бота (не все пользователи)"""

    chat_user = data['message']['chat']['id']

    result_text = f"Сессия устарела или команда неизвестна"
    res = {'chat_id': data['message']['chat']['id'], 'text': result_text}
    message = {'chat_id': chat_user, 'text': result_text}

    r = requests.post(bot.api_url, data=json.dumps(message), headers=bot.headers)
    assert r.status_code == 200

    reply_markup = settings_user.template_remove_keboard()
    message = {'chat_id': chat_user, 'text': 'Перезагрузка на стартовую страницу /start',
               'reply_markup': reply_markup}

    r = requests.post(bot.api_url, data=json.dumps(message), headers=bot.headers)
    assert r.status_code == 200

    result_text = f"Hi {emoji.emojize(':waving_hand:')} .Коммент можно написать через точку"
    reply_markup = settings_user.template_start()
    message = {'chat_id': chat_user, 'text': result_text, 'reply_markup': reply_markup}
    return message, bot.api_url


@bottle.route('/api/v1/echo', method='POST')
def do_echo():
    """ Main """

    logging.info('Do echo')
    message = {}
    curl = None

    try:
        dredis.variable_init(bot)  # get or set settings users regions to bot.dict_init
        bot.subscription = dredis.read_subscription()  # get subscriptions
    except Exception as ex:
        logging.info(f'Error load from Redis: {ex}')
    # logging.info(bot.subscription)

    data = request.json
    # logging.info(data)

    if bot.last_id < data['update_id']:
        bot.last_id = data['update_id']  # Отсекаем старые сообщения

        if data.get('callback_query'):
            # curl = bot.api_answer
            user_start_update(data['callback_query']['message']['chat']['id'],
                              data['callback_query']['from'])

            if ord := data['callback_query'].get('data'):
                logging.info('Callback_query')
                logging.info(ord)
                if exec_func := dp.pull_callback_commands.get(ord):
                    message, curl = exec_func(data, ord)
                else:
                    message, curl = dummy_callback(data)

        if data.get('message'):
            # curl = bot.api_url
            if ord := data['message'].get('text'):
                chat_user = user_start_update(data['message']['chat']['id'],
                                              data['message']['from'])
                chat_user.put_redis_last_message_id(data)
                bot.users[chat_user.__name__] = chat_user

                logging.info('Message')
                logging.info(chat_user.FSM)
                logging.info(ord)
                logging.info(chat_user.call_fsm)

                if exec_func := chat_user.pull_user_commands.get(ord):
                    message, curl = exec_func(data, ord)
                elif exec_func := dp.pull_message_commands.get(ord):
                    # logging.info(ord)
                    message, curl = exec_func(data, ord)
                else:
                    logging.info(ord)
                    logging.info(bot.rdot_three)

                    if bot.rdot_three == ord[0:3]:
                        logging.info('# number seal')
                        message, curl = insert_seal(data, ord)  # add number seal

                    elif bot.rdot == ord[0:1]:
                        logging.info('# comment')
                        message, curl = comment_additional(data, ord)  # add comment

                    elif chat_user.FSM:
                        if exec_func := dp.pull_message_commands.get(ord):
                            chat_user.FSM = False
                            chat_user.previous_ord = None
                            chat_user.call_fsm = None
                            chat_user.fsm_location = [None, None]
                            logging.info('Bad FSM')
                            # Сообщение что ожидался ввод строки
                            message, curl = dummy_message(data)
                        else:
                            # Start FSM
                            message, curl = chat_user.call_fsm(data, ord)

                    else:
                        logging.info('Ожидается перезагрузка на стартовую страницу')
                        message, curl = reload_bot(data)

        if message and curl:
            try:
                r = requests.post(curl, data=json.dumps(message), headers=bot.headers)
                assert r.status_code == 200
                # logging.info(r.content)
                # handler_response_ok(r)  # Обработчик ответа

            except Exception as ex:
                logging.info(str(r))
                logging.error('Error' + str(ex))

    # logging.info('old_message')
    # logging.info(data)


if __name__ == '__main__':
    URL_BOT = PROD
    set_webhook(URL_BOT, input('Please, Input API_TOKEN > '))
