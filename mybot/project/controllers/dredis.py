import os
import json
import logging
import redis
import msgpack

from mybot.config import RESOURCES_PATH


FORMAT = '%(module)s - %(funcName)s -%(lineno)d - %(message)s'
logging.basicConfig(format=FORMAT, level=logging.INFO)


def variable_init(bot):
    """
        Load Data from data.txt (json) and save or get data from redis variable
    """
    redisClient = redis.from_url(os.environ.get("REDIS_URL"))

    if redisClient.exists("settings_data"):
        logging.info('Get settings data from Redis')
        bot.dict_init = msgpack.unpackb(redisClient.get('settings_data'))
        #logging.info(bot.dict_init)
    else:
        logging.info('No settings data, Redis')
        file_path = [RESOURCES_PATH, 'settings', 'data.txt']
        djs = os.path.join(*file_path)

        with open(djs) as json_file:
            newDict = json.load(json_file)

        # save to redis
        redisClient.set('settings_data', msgpack.packb(newDict))
        logging.info('Save settings data to Redis')
        bot.dict_init = newDict
        # logging.info(newDict['city'])
        # logging.info(newDict['adr'])


def save_variable(newDict):

    redisClient = redis.from_url(os.environ.get("REDIS_URL"))

    if redisClient.exists("settings_data"):
        logging.info("save to redis")
        redisClient.set('settings_data', msgpack.packb(newDict))


def read_variable():
    redisClient = redis.from_url(os.environ.get("REDIS_URL"))

    tmp_ = None
    if redisClient.exists("settings_data"):
        tmp_ = msgpack.unpackb(redisClient.get('settings_data'))
    return tmp_


def clear_base_redis():
    # Clear base Redis
    redisClient = redis.from_url(os.environ.get("REDIS_URL"))
    for key in redisClient.keys('*'):
        logging.info(key)
        redisClient.delete(key)


def reload_base_redis(bot):
    # Reload base Redis
    redisClient = redis.from_url(os.environ.get("REDIS_URL"))

    file_path = [RESOURCES_PATH, 'settings', 'data.txt']
    djs = os.path.join(*file_path)

    newDict = {}

    with open(djs) as json_file:
        logging.info('json read finish')
        newDict = json.load(json_file)

    # save to redis
    redisClient.set('settings_data', msgpack.packb(newDict))
    bot.dict_init = newDict
    logging.info('Reload base Redis Done!')


def save_subscription(newDict):
    redisClient = redis.from_url(os.environ.get("REDIS_URL"))
    redisClient.set('subscription', msgpack.packb(newDict))


def read_subscription():
    redisClient = redis.from_url(os.environ.get("REDIS_URL"))
    tmp_ = {}
    if redisClient.exists("subscription"):
        tmp_ = msgpack.unpackb(redisClient.get('subscription'))
    return tmp_


# clear_base_redis()