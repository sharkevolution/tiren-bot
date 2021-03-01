import os
import json
import logging
import redis
import msgpack

from mybot.config import RESOURCES_PATH


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)


def variable_init(bot):
    """
        Load Data from data.txt (json) and save or get data from redis variable
    """
    logging.info('Variable Init')
    redisClient = redis.from_url(os.environ.get("REDIS_URL"))

    if redisClient.exists("settings_data"):
        logging.info('Get settings data from Redis')
        bot.dict_init = msgpack.unpackb(redisClient.get('settings_data'))
        # logging.info(bot.dict_init)
    else:
        logging.info('No settings data, Redis')
        file_path = [RESOURCES_PATH, 'settings', 'data.txt']
        djs = os.path.join(*file_path)

        with open(djs) as json_file:
            newDict = json.load(json_file)

        # save to redis
        redisClient.set('settings_data', msgpack.packb(newDict))
        logging.info('Save settings data from Redis')
        bot.dict_init = newDict
        # logging.info(newDict)


def save_variable(newDict):

    redisClient = redis.from_url(os.environ.get("REDIS_URL"))

    if redisClient.exists("settings_data"):
        # save to redis
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
        redisClient.delete(key)


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