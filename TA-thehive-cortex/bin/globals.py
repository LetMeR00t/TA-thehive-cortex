# encoding = utf-8

def initialize_globals(log_content_input="[]"):
    global log_context
    global log_id
    log_context = log_content_input
    log_id = 0

def next_log_id():
    global log_id
    log_id += 1
    str_log_id = str(log_id)
    return "0"*(6-len(str_log_id))+str(log_id)