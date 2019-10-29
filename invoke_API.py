import csv
import random
import string
import requests
import time
from datetime import datetime
from faker import Factory
import threading
import multiprocessing
import sys
import argparse
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

parser = argparse.ArgumentParser("run traffic tool")
parser.add_argument("filename", help="Enter a filename to write final output", type=str)
parser.add_argument("runtime", help="Enter the script execution time in minutes", type=float)
args = parser.parse_args()
filename = args.filename + ".csv"
script_runtime = args.runtime * 60       # in seconds


# Configurations
# script_runtime = 10 * 60       # in seconds
no_of_threads = 20
active_threads = 0
max_connection_refuse_count = 50

# Variables
script_starttime = None
user_ip = {}
user_cookie = {}
users_apps = {}
scenario_pool = []
pool_lock = multiprocessing.Lock()
connection_refuse_count = 0

fake_generator = Factory.create()


'''
    This function will write the given log output to the log.txt file
'''
def log(tag, write_string):
    with open('logs/log.txt', 'a+') as file:
        file.write("[{}] ".format(tag) + str(datetime.now()) + ": " + write_string + "\n")


'''
    This method will return an integer slightly varied to the given median
'''
def varySlightly(median, no_of_users):
    lower_bound = int(median) - int(int(no_of_users)/2)
    upper_bound = int(median) + int(int(no_of_users)/2)
    if lower_bound <= 0:
        lower_bound = 1
    req_count = random.randint(lower_bound,upper_bound)

    return req_count


'''
    This method will return a randomly generated ipv4 address
'''
def ipGen():
    # return "{}.{}.{}.{}".format(random.randint(1,255), random.randint(0,255), random.randint(0,255), random.randint(0,255))
    return fake_generator.ipv4()


'''
    This method will return a randomly generated cookie
'''
def getCookie():
    lettersAndDigits = string.ascii_lowercase + string.digits
    cookie = 'JSESSIONID='
    cookie += ''.join( random.choice(lettersAndDigits) for ch in range(31) )
    return cookie


'''
    This method will return a list of unique ipv4 addresses
'''
def genUniqueIPList(count:int):
    ip_list = []
    for ip in range(count):
        ip_list.append(ipGen())

    unique_list = list(set(ip_list))

    while( len(unique_list) != len(ip_list) ):
        diff = len(ip_list) - len(unique_list)

        for i in range(diff):
            unique_list.append(ipGen())
        unique_list = list(set(unique_list))

    # writing list of ips to a file
    ip_all_str = "ip_address\n"
    for ip in unique_list:
        ip_all_str += ip + "\n"
    with open('dataset/ip_list_{}'.format(filename), 'w') as file:
        file.write(ip_all_str)

    return unique_list


'''
    This method will return a list of unique cookies
'''
def genUniqueCookieList(count:int):
    cookie_list = []
    for cookie in range(count):
        cookie_list.append(getCookie())

    unique_list = list(set(cookie_list))

    while( len(unique_list) != len(cookie_list) ):
        diff = len(cookie_list) - len(unique_list)

        for i in range(diff):
            unique_list.append(getCookie())
        unique_list = list(set(unique_list))

    return unique_list


'''
    This method will send http requests to the given address: GET, POST only
'''
def sendRequest(url_ip, url_port, api_name, api_version, path, access_token, method, user_ip, cookie, app_name, username):
    url = "https://{}:{}/{}/{}/{}".format(url_ip, url_port, api_name, api_version, path)
    headers = {
        'accept': 'application/json',
        'Authorization': 'Bearer {}'.format(access_token),
        'client-ip': '{}'.format(user_ip),
        'x-forwarded-for': '{}'.format(user_ip),
        'cookie': '{}'.format(cookie)
    }
    code = None
    res_txt = ""

    try:
        if method=="GET":
            response = requests.get(url=url, headers=headers, verify=False)
            code = response.status_code
            res_txt = response.text
        elif method=="POST":
            data = {"Payload": "sample"}
            response = requests.post(url=url, headers=headers, data=data, verify=False)
            code = response.status_code
            res_txt = response.text
        else:
            code = '400'
            res_txt = 'Invalid type!'
    except ConnectionRefusedError:
        log("ERROR", "HTTP Connection Refused!")
        code = '404'

    # write data to files
    write_string = ""               # api_name,access_token,ip,cookie,path,method
    write_response = ""

    write_string = api_name + "," + access_token + "," + user_ip + "," + cookie + "," + api_name+"/"+api_version+"/"+path + "," + method + "\n"
    write_response = str(code) + "," + res_txt + "," + app_name + "," + api_name + "," + username + "," + access_token + "\n"

    with open('dataset/{}'.format(filename), 'a+') as file:
        file.write(write_string)

    with open('response/res_{}'.format(filename), 'a+') as file:
        file.write(write_response)

    return code,res_txt


'''
    This method will return a random integer between zero and ten.
    Highly biased for returning zero.
'''
def randomSleepTime():
    int_list = [0,0,0,0,0,0,1,0,2,3,60*2,0,0,4,5,0,0,0,5,2,0,60*10,0,0,0,1,0,0,0,0,0]
    return int_list[random.randint(0,30)]


'''
    This thread will take an available scenario from the pool and execute it
'''
class ScenarioExecutor(threading.Thread):
    def __init__(self, threadID, name, lock):
        global pool_lock
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.starttime = datetime.now()
        pool_lock = lock

    def run(self):
        global scenario_pool, connection_refuse_count, script_starttime, script_runtime, active_threads

        log("INFO", "Scenario thread {} started!".format(self.name))
        while True:
            pool_lock.acquire()
            scenario_row = scenario_pool.pop(0)
            pool_lock.release()

            no_of_requests = scenario_row[0]
            api_name = scenario_row[1]
            api_version = scenario_row[2]
            path = scenario_row[3]
            access_token = scenario_row[4]
            method = scenario_row[5]
            user_ip = scenario_row[6]
            cookie = scenario_row[7]
            app_name = scenario_row[8]
            username = scenario_row[9]

            for i in range(no_of_requests):
                try:
                    res_code, res_txt = sendRequest("10.100.4.187", "8243", api_name, api_version, path, access_token, method, user_ip, cookie, app_name, username)
                    time.sleep(randomSleepTime())
                except:
                    connection_refuse_count += 1
                    if connection_refuse_count > max_connection_refuse_count:
                        log("ERROR", "Terminating the thread due to maximum no of connection refuses!")
                        active_threads -= 1
                        sys.exit()

            pool_lock.acquire()
            scenario_pool.append(scenario_row)
            pool_lock.release()

            # break
            up_time = datetime.now() - script_starttime
            if up_time.seconds >= script_runtime:
                log("INFO", "{} stopped. Execution finished!".format(self.name))
                active_threads -= 1
                break


'''
    Execute the scenario and generate the dataset
    Usage: python3 generate_invokeData.py
    output folder: dataset/
'''

# generate set of ips and cookies for each user
with open('APIM_scenario/data/user_generation.csv') as file:
    userlist = file.read().split('\n')

    ip_list = genUniqueIPList(len(userlist))
    cookie_list = genUniqueCookieList(len(userlist))

    for user in userlist:
        username = user.split('$$ ')[0]
        user_ip.update( {username: ip_list.pop()} )
        user_cookie.update( {username: cookie_list.pop()} )

# update dictionary for apps and their users
with open('APIM_scenario/data/app_creation.csv') as file:
    appList = file.read().split('\n')

    for app in appList:
        if app != "":
            appName = app.split('$ ')[0]
            users_apps.update( {appName: []} )

# set ips with username, access tokens and append to relevant lists
with open('APIM_scenario/api_invoke_tokens.csv') as file:
    user_token = csv.reader(file)

    for row in user_token:
        username = row[0]
        app_name = row[1]
        token = row[2]
        ip = user_ip.get(username)
        cookie = user_cookie.get(username)

        (users_apps[app_name]).append([username,token,ip,cookie])

with open('dataset/{}'.format(filename), 'w') as file:
    file.write("timestamp,api,access_token,ip_address,cookie,invoke_path,http_method\n")

# generate scenario data according to the script and append to the pool
with open('APIM_scenario/data/api_invoke_scenario.csv') as file:
    scenario_data = csv.reader(file, delimiter='$')

    for row in scenario_data:
        app_name = row[0]
        invokes = row[1]
        invokes = invokes.strip('][').split("],[")

        user_count = int(invokes[0].split(',')[0])
        users = []
        for i in range(user_count):
            users.append(users_apps.get(app_name).pop())

        for invoke in invokes:
            row2 = invoke.split(',')
            api_name = row2[1]
            method = row2[2]
            call_median = int(row2[3])
            path = row2[4]
            api_version = "1"
            full_path = api_name + "/" + api_version + "/" + path + "/"

            for user in users:              # user[username,token,ip,cookie]
                no_of_requests = varySlightly(call_median, user_count)
                scenario_pool.append([no_of_requests, api_name, "1", path, user[1], method, user[2], user[3], app_name, user[0]])

# record script starttime
script_starttime = datetime.now()

# create and start threads
for i in range(no_of_threads):
    thread = ScenarioExecutor(i, 'thread_{}'.format(i), pool_lock)
    thread.start()
    active_threads += 1

print("[INFO] Scenario loaded successfully. Wait {} minutes before closing the terminal!".format(str(script_runtime/60)))
log("INFO", "Scenario loaded successfully. Wait {} minutes before closing the terminal!".format(str(script_runtime/60)))

while True:
    uptime = datetime.now() - script_starttime
    if uptime.seconds >= script_runtime:
        print("[INFO] Script terminated successfully. uptime:{} minutes".format(uptime.seconds/60.0))
        log("INFO", "Script terminated successfully. uptime:{} minutes".format(uptime.seconds/60.0))
        break
    if active_threads != 0:
        time.sleep(5)
    else:
        if connection_refuse_count < max_connection_refuse_count:
            print("[INFO] Script completed successfully!")
            log("INFO", "Script completed successfully!")
        else:
            print("[ERROR] Program terminated!")
        break
