import discord
import asyncio
import os
import sys
from dotenv import load_dotenv
from pubsub import pub
import meshtastic
import meshtastic.tcp_interface
import meshtastic.serial_interface
import queue
import time
from datetime import datetime

load_dotenv()
token = os.getenv("DISCORD_TOKEN")
channel_id = int(os.getenv("DISCORD_CHANNEL_ID"))
meshtastic_hostname = os.getenv("MESHTASTIC_HOSTNAME")

meshtodiscord = queue.Queue()
discordtomesh = queue.Queue()
nodelistq = queue.Queue()

def onConnectionMesh(interface, topic=pub.AUTO_TOPIC):  
    """called when we (re)connect to the meshtastic radio"""
    print(interface.myInfo)

def onReceiveMesh(packet, interface):  
    """called when a packet arrives from mesh"""
    try: 
        if packet['decoded']['portnum']=='TEXT_MESSAGE_APP': #only interest in text packets for now
            meshtodiscord.put("Node "+packet['fromId']+" writes to node "+packet['toId']+ " this message: " +packet['decoded']['text'])
    except KeyError as e: #catch empty packet
        pass

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self) -> None:
        # create the background task and run it in the background
        self.bg_task = self.loop.create_task(self.my_background_task())

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    async def on_connection(self):  # pylint: disable=unused-argument
        # nothing to do here
        return


    async def on_message(self, message):
        if message.author.id == self.user.id:
            return

        if message.content.startswith('$help'):
            helpmessage="Meshtastic Discord Bridge is up.  Command list:\n"\
                "$sendprimary <message> sends a message up to 225 characters to the the primary channel\n"\
                "$send nodenum=########### <message> sends a message up to 225 characters to nodenum ###########\n"\
                "$activenodes will list all nodes seen in the last 15 minutes"
            await message.channel.send(helpmessage)

        if message.content.startswith('$sendprimary'):
            tempmessage=str(message.content)
            tempmessage=tempmessage[tempmessage.find(' ')+1:225] #could be 228
            await message.channel.send('Sending the following message to the primary channel:\n'+tempmessage)
            discordtomesh.put(tempmessage)

        if message.content.startswith('$send nodenum='):
            tempmessage=str(message.content)
            nodenumstr=tempmessage[14:tempmessage.find(' ',14)+1]
            tempmessage=tempmessage[tempmessage.find(' ',14)+1:225] #could be 228
            try:
                nodenum=int(nodenumstr)
                await message.channel.send('Sending the following message:\n'+tempmessage+'\nto nodenum:\n'+str(nodenum))
                discordtomesh.put("nodenum="+str(nodenum)+ " "+tempmessage)
            except:
                await message.channel.send('Could not send message')
                 
 

        if message.content.startswith('$activenodes'):
            nodelistq.put("just pop a message on this queue so we know to send nodelist to discord")


    async def my_background_task(self):
        await self.wait_until_ready()
        counter = 0
        nodelist=""
        channel = self.get_channel(channel_id) 
        pub.subscribe(onReceiveMesh, "meshtastic.receive")
        pub.subscribe(onConnectionMesh, "meshtastic.connection.established")
        try:
            if len(meshtastic_hostname)>1:
                print("Trying TCP interface to "+meshtastic_hostname)
                iface = meshtastic.tcp_interface.TCPInterface(meshtastic_hostname)
            else:
                print("Trying serial interface")
                iface =  meshtastic.serial_interface.SerialInterface()
        except Exception as ex:
            print(f"Error: Could not connect {ex}")
            sys.exit(1)
        while not self.is_closed():
            counter += 1
            print(counter)
            if (counter%12==1):
                #approx 1 minute (every 12th call, call every 5 seconds), refresh node list
                nodelist="Nodes seen in the last 15 minutes\n"
                nodes=iface.nodes
                for node in nodes:
                    try:
                            id = str(nodes[node]['user']['id'])
                            num = str(nodes[node]['num'])
                            longname = str(nodes[node]['user']['longName'])
                            if "hopsAway" in nodes[node]:
                                hopsaway = str(nodes[node]['hopsAway'])
                            else:
                                hopsaway="0"
                            if "snr" in nodes[node]:
                                snr = str(nodes[node]['snr'])
                            else:
                                snr="?"
                            if "lastHeard" in nodes[node]:
                                ts=int(nodes[node]['lastHeard'])
                                timestr = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                            else:
                                #Just make it old so it doesn't show, only interested in nodes we know are active
                                ts=time.time()-(16*60)
                                timestr="Unknown"
                            #if ts>time.time()-(15*60):
                            if len(nodelist+"\nid:"+id + ", num:"+num+", longname:" + longname + ", hops:" + hopsaway + ", snr:"+snr+", lastheardutc:"+timestr )<1900:
                                nodelist=nodelist+"\nid:"+id + ", num:"+num+", longname:" + longname + ", hops:" + hopsaway + ", snr:"+snr+", lastheardutc:"+timestr 
                            else:
                                print("Nodelist exceeds 1900 characters.... cutting at 1900")
                            print(nodelist)
                    except KeyError as e:
                        print(e)
                        pass
            try:
                meshmessage=meshtodiscord.get_nowait()
                await channel.send(meshmessage)
                meshtodiscord.task_done()
            except queue.Empty:
                pass
            try:
                meshmessage=discordtomesh.get_nowait()
                if meshmessage.startswith('nodenum='):
                    nodenum=int(meshmessage[8:meshmessage.find(' ')])
                    iface.sendText(meshmessage[meshmessage.find(' ')+1:],destinationId=nodenum)
                else:    
                    iface.sendText(meshmessage)
                discordtomesh.task_done()
            except: #lets pass on both the empty queue and the int conversion
                pass
            try:
                nodelistq.get_nowait()
                #if there's any item on this queue, we'll send the nodelist
                await channel.send(nodelist)
                nodelistq.task_done()
            except queue.Empty:
                pass
            await asyncio.sleep(5) 
        
intents=discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
client.run(token)
