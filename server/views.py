import datetime
import json
import logging
import math
import os
import re
from random import randint
from uuid import UUID

import flask
import flask_login
from flask import request, render_template, redirect
from flask_login import login_required
from flask_mongoengine.wtf import model_form
from flask_mongoengine.wtf.fields import ModelSelectField
from flask_mongoengine.wtf.orm import ModelConverter, converts
from wtforms import validators

import logging_server
import models
import task_manager
from finik.crypto_data import CryptoDataProvider
from finik.cryptonator import Cryptonator
from bestminer.server_commons import assert_expr
from models import User, Rig, PoolAccount, MinerProgram, ConfigurationGroup
# DEFAULT_CONFIGURATION_GROUP = "ETH(poloniex)"
from task_manager import get_miner_config_for_configuration










