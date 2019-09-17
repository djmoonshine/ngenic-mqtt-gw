import requests
import paho.mqtt.client as mqtt
import json
import time

room_tune = {}
room_node = {}
tune_controller = {}
tune_name = {}
baseurl = "https://app.ngenic.se/api/v3/"


def set_temperature(room_uuid, temp):
    tune_uuid = room_tune[room_uuid]
    data = {"targetTemperature": temp}
    url = baseurl + "/tunes/" + tune_uuid+ "/rooms/" + room_uuid
    try:
        response = requests.put(url, json=data, headers=headers)
    except:
        print("Error communicating with api")

    print("Http status response " + str(response.status_code))
    #time.sleep(1)
    send_state()


def send_ha_mqtt_discovery(roomuuid, name):
    msg = {
        "name": name,
        "availability_topic": "homeassistant/climate/" + roomuuid + "/available",
        "pl_avail": "online",
        "pl_not_avail": "offline",
        "temp_cmd_t": "homeassistant/climate/" + roomuuid + "/setTemp",
        "temp_stat_t": "homeassistant/climate/" + roomuuid + "/state/target_temp",
        "curr_temp_t": "homeassistant/climate/" + roomuuid + "/state/measured_temp",
        "min_temp": "15",
        "max_temp": "25",
        "temp_step": "0.5",
        "modes": ["heat"]
    }
    print("Publishing " + str(msg).replace("'", '"'))
    client.publish("homeassistant/climate/" + roomuuid + "/config", str(msg).replace("'", '"'))
    print("Subscibing to topics")
    client.subscribe("homeassistant/climate/" + roomuuid + "/setTemp")
    client.message_callback_add("homeassistant/climate/" + roomuuid + "/setTemp", set_temp_callback)


def send_ha_temp_mqtt_discovery(controller_uuid, name):
    print("Sending mqtt discover meaage for temp sensor" + name)
    msg = {
        "state_topic": "homeassistant/sensor/" + controller_uuid + "/state",
        "name": name,
        "unit_of_measurement": "°C"
    }
    print("Publishing " + str(msg).replace("'", '"'))
    client.publish("homeassistant/sensor/" + controller_uuid + "/config", str(msg).replace("'", '"'))


def set_temp_callback(client, userdata, message):
    print("Temp callback ")
    topic = str(message.topic)
    #Extract room uuid from topic string
    room_uuid = topic.split("/")[2]
    print("Changning temp om room uuid " + room_uuid)
    message.payload = message.payload.decode("utf-8")
    temp = round(float(message.payload),1)
    print("Setting temperature to: " + str(temp))
    set_temperature(room_uuid,float(temp))
    #time.sleep(5)
    #send_state()


def on_connect(clientt, userdata, flags, rc):
    if rc == 0:
        print("Connected to broker")
        #client.subscribe("homeassistant/climate/" + device + "/setMode")
        #client.message_callback_add("homeassistant/climate/" + device + "/setMode", set_mode_callback)


def send_state():
    for room, node in room_node.items():
        #Get room target temperature
        room_status_url = baseurl + "tunes/" + room_tune[room] + "/rooms/" + room
        room_status = requests.get(room_status_url, headers=headers)
        room_json = json.loads(room_status.text)
        target_temp = room_json["targetTemperature"]

        #Get node mesured temperature
        node_temp_url = baseurl + "tunes/" + room_tune[room] + "/measurements/" + node + "/latest?type=temperature_C"
        node_temp_response = requests.get(node_temp_url, headers=headers)
        node_temp_json = json.loads(node_temp_response.text)
        measured_temp = node_temp_json["value"]
        print("Updating state for room uuid " + room)
        print("Target temp: " + str(target_temp))
        print("Measured temp: " + str(measured_temp))
        client.publish("homeassistant/climate/" + room + "/state/target_temp", str(target_temp))
        client.publish("homeassistant/climate/" + room + "/state/measured_temp", str(measured_temp))
        client.publish("homeassistant/climate/" + room + "/available", "online")

def send_temp():
    for tune, controller in tune_controller.items():
        get_temp_url = baseurl + "tunes/" + tune + "/measurements/" + controller + "/latest?type=temperature_C"
        get_temp_response = requests.get(get_temp_url , headers=headers)
        get_temp_json = json.loads(get_temp_response.text)
        temp = round(get_temp_json["value"],1)
        print("Updating temperature for " + tune_name[tune] + " " + str(temp))
        client.publish("homeassistant/sensor/" + controller + "/state", str(temp))


def get_rooms(tuneUuid):
    url = baseurl + "tunes/" + tuneUuid + "/rooms"
    response = requests.get(url, headers=headers)
    print(response.text)
    room_list = json.loads(response.text)
    for room in room_list:
        room_node[room["uuid"]] = room["nodeUuid"]
        room_tune[room["uuid"]] = tuneUuid
        #print(room_node)
        #print(room_tune)
        send_ha_mqtt_discovery(room["uuid"],room["name"])

#Find and save controller (Node type 1) uuid since outside temperature sensor is connected to it.
def get_controller(tuneuuid):
    print("Finding controller for tune uuid " + tuneuuid)
    nodes_url = baseurl + "tunes/" + tuneuuid + "/gateway/nodes"
    tune_nodes = requests.get(nodes_url, headers=headers)
    tune_nodes_json = json.loads(tune_nodes.text)
    for node in tune_nodes_json:
        print(node)
        if node["type"] == 1:
            print("Found controller uuid: " + node["uuid"])
            tune_controller[tuneuuid] = node["uuid"]


with open('config.json', 'r') as f:
    config = json.load(f)
    token = config['TOKEN']
    mqtt_user = config['MQTT_USER']
    mqtt_pwd = config['MQTT_PWD']
    mqtt_address = config['MQTT_ADDRESS']
#
#
client = mqtt.Client()
client.username_pw_set(mqtt_user, password=mqtt_pwd)
#client.will_set("homeassistant/climate/" + device + "/available","offline",1,retain=False)
client.on_connect = on_connect
print("Connecting to broker")
client.connect(mqtt_address, port=1883, keepalive=60, bind_address="")
last_time = 0
last_discovery_time = time.time()

headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + token,
}
url = baseurl + "tunes"
try:
    response = requests.get(url, headers=headers)
    print(response.text)
    tune_list = json.loads(response.text)
    tunes = response.text
    for tune in tune_list:
        print(tune["tuneUuid"])
        get_rooms(tune["tuneUuid"])
        get_controller(tune["tuneUuid"])
        tune_name[tune["tuneUuid"]] = tune["tuneName"]
        send_ha_temp_mqtt_discovery(tune_controller[tune["tuneUuid"]],tune_name[tune["tuneUuid"]])


except:
    print("Error communicating with api")


while True:
    client.loop_start()
    if time.time() - last_time > 60:
        send_state()
        send_temp()
        last_time = time.time()
    if time.time() - last_discovery_time > 1800:
        last_discovery_time = time.time()
    time.sleep(10)
    client.loop_stop()

