#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import os
import logging

import requests
import gmail
from gmail import Message


def send_mail(base_mail, to_mail, user_name, user_text):
    b = "".join(["Thanks 2018! <", base_mail, ">"])

    if GMAIL_PASS := os.environ.get("GMAIL_PASS"):
        gm = gmail.GMail(b, GMAIL_PASS)
        msg = Message('Спасибо от', to="me <{0}>".format(to_mail),
                      text="Спасибо от {0}, сообщение: {1}".format(user_name, user_text))
        gm.send(msg)


def send_sms(user_name, user_text):

    if password := os.environ.get("SMS_PASS"):
        login = '380732218247'  # phone number
        alphaName = 'gsm1'  # string, sender id (alpha-name)

        abonent = '380732218247'
        text = '2018 Thanks!: name: {0}, txt: {1}'.format(user_name, user_text)

        xml = "<?xml version='1.0' encoding='utf-8'?><request_sendsms><username><![CDATA[" + \
              login + "]]></username><password><![CDATA[" + password + "]]></password><from><![CDATA[" + \
              alphaName + "]]></from><to><![CDATA[" + abonent + "]]></to><text><![CDATA[" + \
              text + "]]></text></request_sendsms>"

        url = 'https://gate.smsclub.mobi/xml/'
        headers = {'Content-type': 'text/xml; charset=utf-8'}

        try:
            res = requests.post(url, data=xml, headers=headers)
        except Exception as ex:
            logging.info(ex)
