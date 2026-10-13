import json
import hashlib
import subprocess
from uuid import uuid4
from urllib.parse import urlparse, parse_qsl

try:
    import html5lib
except ImportError:
    print(f'warning: html5lib module not found')

try:
    from lxml import etree
except ImportError:
    print('warning: lxml module not found')

try:
    import pandas as pd
except ImportError as ie:
    print(f'failed to insert pandas dataframe:: {ie}')


def read_json_config(path):
    """
    load json config file
    :param path:
    :return:
    """
    try:
        with open(path, 'r') as f:
            js = json.load(f)
        return js
    except Exception as e:
        return e


def write_json_config(data, path):
    """
    write dict based config
    :param data:
    :param path:
    :return:
    """
    try:
        if not isinstance(data, dict):
            raise ValueError(f'input data not supported:: {type(data)}')

        with open(path, 'w') as f:
            json.dump(data, indent=4, fp=f)
        return True
    except Exception as e:
        return e


def read_csv_dataset(path):
    """
    create dataframe from input csv-based dataset's path
    :param path:
    :return:
    """
    try:
        df = pd.read_csv(path)
        return df
    except Exception as e:
        return e


def read_pickle_dataset(path):
    """
    create dataframe from input pickle-based dataset's path
    :param path:
    :return:
    """
    try:
        df = pd.read_pickle(path)
        return df
    except Exception as e:
        return e


def get_hash(string):
    """
    create md5 hash from input string/bytes
    :param string:
    :return:
    """
    if isinstance(string, bytes):
        return hashlib.md5(string).hexdigest()
    elif isinstance(string, str):
        return hashlib.md5(string.encode()).hexdigest()


def get_element_tree(string):
    """
    receive html source and return element tree object
    :param string:
    :return:
    """
    try:
        return etree.HTML(string)
    except Exception as e:
        return e


def get_repaired_element_tree(string):
    """
    repair broken html source and return element tree object
    :param string:
    :return:
    """
    try:
        parsed_html = html5lib.parse(string, namespaceHTMLElements=False)
        repaired_html = html5lib.serialize(parsed_html)
        del parsed_html
        return etree.HTML(repaired_html)
    except Exception as e:
        return e


def get_unique_identifier():
    """
    get unique identifier
    :return:
    """
    return str(uuid4())


def get_xpath_txt(xpath, tree):
    """
    parse single string object from element tree
    :param xpath:
    :param tree:
    :return:
    """
    try:
        return ''.join(tree.xpath(xpath)).strip()
    except Exception as e:
        return e


def get_params(url):
    """
    extract query parameters from url and convert them to dict based object
    :param url:
    :return:
    """
    try:
        raw_params = parse_qsl(urlparse(url).query)
        params = dict()
        for param in raw_params:
            params[param[0]] = param[1]

        return params
    except Exception as e:
        return e


def get_wd_proxy_data(proxy_url):
    """
    snippet parse proxy url and prepare it for playwright usage
    input:  http://username:password@proxy.example.com:8080
    output: {'username': 'username', 'password': 'password', 'server': 'proxy.example.com:8080'}

    :param proxy_url:
    :return:
    """
    try:
        p = urlparse(proxy_url)
        prx = dict()
        prx['username'] = p.username if p.username else ''
        prx['password'] = p.password if p.password else ''
        prx['server'] = p.netloc.split('@')[-1] if p.netloc.split('@')[-1] else proxy_url
        del p
        return prx
    except Exception as e:
        return e


def get_all_keys_data(config, search_key):
    """
    Snippet performs recursive search for some key on all levels of the dictionary based object
    :param config:
    :param search_key:
    :return:
    """
    all_files = []
    for key, value in config.items():
        if isinstance(value, dict):
            all_files.extend(get_all_keys_data(value, search_key))
        elif key == search_key:
            if isinstance(value, list):
                all_files.extend(value)
    return all_files


def execute_cmd(cmd):
    """
    Execute a bash command return exception if command failed
    :param cmd:
    :return:
    """
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()
    try:
        if process.returncode == 0:
            return True
        else:
            raise ValueError(f'command execution finished with errors :: {err.decode("utf-8")}')

    except Exception as e:
        return e
