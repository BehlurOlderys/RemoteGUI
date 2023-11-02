import json
import os
import logging


logger = logging.getLogger(__name__)


config_file_path = "config.json"


def read_json_file_content(fp):
    with open(fp, 'r') as infile:
        return json.load(infile)


def read_config():
    return read_json_file_content(config_file_path)


def save_config(c):
    with open(config_file_path, 'w') as outfile:
        json.dump(c, outfile)


def write_empty_config_to_file(fp):
    with open(fp, 'w') as outfile:
        json.dump({}, outfile)


def init_config():
    if not os.path.isfile(config_file_path):
        logger.debug("Writing new config file")
        write_empty_config_to_file(config_file_path)
