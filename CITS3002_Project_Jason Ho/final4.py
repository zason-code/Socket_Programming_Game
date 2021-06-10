# CITS3002 2021 Assignment
#
# This file implements a basic server that allows a single client to play a
# single game with no other participants, and very little error checking.
#
# Any other clients that connect during this time will need to wait for the
# first client's game to complete.
#
# Your task will be to write a new server that adds all connected clients into
# a pool of players. When enough players are available (two or more), the server
# will create a game with a random sample of those players (no more than
# tiles.PLAYER_LIMIT players will be in any one game). Players will take turns
# in an order determined by the server, continuing until the game is finished
# (there are less than two players remaining). When the game is finished, if
# there are enough players available the server will start a new game with a
# new selection of clients. Done by: Jason Ho, 22360143

import socket
import sys
import tiles
import threading
import queue
import time
import random

#NO_OF_PLAYERS_PLAY = 6 
board = tiles.Board()
player_list = [] #List containing active players
playerid = [] #List/Queue for player ids
player_no = 0
thread_pool = [] #List containing threads
player_turn=0
buffer_playerlist =[] #Global list containing ALL players
spectator_list = [] #List containing inactive/spectators
gameStart = False # has the game started yet
number_of_connections=0
thread1helper = False #prevent thread1 from going ahead and for current implementation to work
# timeout timer from the internet. 
def countdown(t):
    
  while t:
    mins, secs = divmod(t, 60)
    timer = '{:02d}:{:02d}'.format(mins, secs)
    print(timer, end="\r")
    time.sleep(1)
    t -= 1
# Player class to hold client info
class Player:

  def __init__(self,player_id,conn,address,name):
    self.player = player_id
    self.conn = conn
    self.address = address
    self.name= name

def client_handler(connection, address,pl):
  global player_turn
  global playerid
  global player_list
  global spectator_list
  global buffer_playerlist
  global gameStart
  global thread1helper
  host, port = address
  name = '{}:{}'.format(host, port)

  idnum=pl
  live_idnums = playerid
  
  #broadcast to everyone
  connection.send(tiles.MessageWelcome(idnum).pack())
  for i in range(len(buffer_playerlist)):
    buffer_playerlist[i].conn.send(tiles.MessagePlayerJoined(name, idnum).pack())
    
  for i in range(len(buffer_playerlist)):
    connection.send(tiles.MessagePlayerJoined(buffer_playerlist[i].name, buffer_playerlist[i].player).pack())
  
  connection.send(tiles.MessagePlayerJoined(name,idnum).pack())
  new_Player = Player(idnum,connection,address,name)
  buffer_playerlist.append(new_Player)
  player_list = buffer_playerlist[:2]
  print(player_list)
  spectator_list = buffer_playerlist[2:len(buffer_playerlist)]

  if (thread1helper==False) and len(buffer_playerlist)==2:
    for i in range(len(buffer_playerlist)):
      playerid.append(buffer_playerlist[i].player)
    thread1helper=True

  time.sleep(2)
  connection.send(tiles.MessageGameStart().pack())

  for _ in range(tiles.HAND_SIZE):
    tileid = tiles.get_random_tileid()
    connection.send(tiles.MessageAddTileToHand(tileid).pack())

  for i in range(len(player_list)):
    player_list[i].conn.send(tiles.MessagePlayerTurn(playerid[0]).pack())
  for i in range(len(spectator_list)):
    spectator_list[i].conn.send(tiles.MessagePlayerTurn(playerid[0]).pack())

  buffer = bytearray()
  
  while True:
    #reset after each game is completed
    if len(playerid)<=1:
      # 5s countdown between games
      #countdown(int(5))

      if(len(playerid)==1):
        playerid.pop(0) #clearing the playerid queue
      board.reset() #reset the board
      
      random.shuffle(buffer_playerlist) #shuffle again, randomize order. 
      player_list = buffer_playerlist[:4] #max of 4 players can play the game
      spectator_list = buffer_playerlist[4:len(buffer_playerlist)]
      #broadcast everything again
      for i in range(len(player_list)):
        player_list[i].conn.send(tiles.MessagePlayerJoined(name, idnum).pack())
      for i in range(len(spectator_list)):
        spectator_list[i].conn.send(tiles.MessagePlayerJoined(name, idnum).pack())

      for i in range(len(player_list)):
        playerid.append(player_list[i].player)

      for p in player_list:
        p.conn.send(tiles.MessageGameStart().pack())

      for p in spectator_list:
        p.conn.send(tiles.MessageGameStart().pack())

      for p in player_list:
        for _ in range(tiles.HAND_SIZE):
          tileid = tiles.get_random_tileid()
          p.conn.send(tiles.MessageAddTileToHand(tileid).pack())
      
      for p in spectator_list:
        for _ in range(tiles.HAND_SIZE):
          tileid = tiles.get_random_tileid()
          p.conn.send(tiles.MessageAddTileToHand(tileid).pack())
      
      for p in player_list:
        p.conn.send(tiles.MessagePlayerTurn(playerid[0]).pack())

      for p in spectator_list:
         p.conn.send(tiles.MessagePlayerTurn(playerid[0]).pack())

      

    chunk = connection.recv(4096)
    
    if not chunk:
      # If client disconnects mid-way through the game. 
      # Remove from queue, active_playerlists etc
      # broadcast that client is eliminated
      if playerid[0]==idnum:
        for i in range(len(player_list)):
          if(idnum == player_list[i].player):
            playerid.remove(idnum)
            buffer_playerlist.remove(player_list[i])
            player_list.remove(player_list[i])
          for i in range(len(player_list)):
            player_list[i].conn.send(tiles.MessagePlayerTurn(playerid[0]).pack())

          for i in range(len(spectator_list)):
            spectator_list[i].conn.send(tiles.MessagePlayerTurn(playerid[0]).pack())
      else:
        for i in range(len(spectator_list)):
          if(idnum == spectator_list[i].player):
            buffer_playerlist.remove(spectator_list[i])
            spectator_list.remove(spectator_list[i])
        for i in range(len(player_list)):
          player_list[i].conn.send(tiles.MessagePlayerEliminated(idnum).pack())

        for i in range(len(spectator_list)):
          spectator_list[i].conn.send(tiles.MessagePlayerEliminated(idnum).pack())


      number_of_connections-=1
      print('client {} disconnected'.format(address))
      return

    buffer.extend(chunk)

    while True:
      
      msg, consumed = tiles.read_message_from_bytearray(buffer)
      if not consumed:
        break

      buffer = buffer[consumed:]

      print('received message {}'.format(msg))

      # sent by the player to put a tile onto the board (in all turns except
      # their second)
      if isinstance(msg, tiles.MessagePlaceTile) and playerid[0]==idnum:
        #print(player_turn)
        if board.set_tile(msg.x, msg.y, msg.tileid, msg.rotation, msg.idnum):
          # notify client that placement was successful
          for i in range(len(player_list)):
            player_list[i].conn.send(msg.pack())
          for i in range(len(spectator_list)):
            spectator_list[i].conn.send(msg.pack())
          
          playerid.pop(0)
          playerid.append(idnum)

          # check for token movement
          positionupdates, eliminated = board.do_player_movement(live_idnums)

          for msg in positionupdates:
            
            for i in range(len(player_list)):
              player_list[i].conn.send(msg.pack())
            for i in range(len(spectator_list)):
              spectator_list[i].conn.send(msg.pack())
          
          for j in eliminated:
            
            for i in range(len(player_list)):
              player_list[i].conn.send(tiles.MessagePlayerEliminated(j).pack())
            playerid.remove(j)
            for i in range(len(spectator_list)):
              spectator_list[i].conn.send(tiles.MessagePlayerEliminated(j).pack())
            #return
          if not playerid:
            break

          # pickup a new tile
          tileid = tiles.get_random_tileid()
          connection.send(tiles.MessageAddTileToHand(tileid).pack())

          # start next turn
          for i in range(len(player_list)):
            player_list[i].conn.send(tiles.MessagePlayerTurn(playerid[0]).pack())
          for i in range(len(spectator_list)):
            spectator_list[i].conn.send(tiles.MessagePlayerTurn(playerid[0]).pack())
          

      # sent by the player in the second turn, to choose their token's
      # starting path
      elif isinstance(msg, tiles.MessageMoveToken) and idnum==playerid[0]:
        #print("token " +str(player_turn))
        if not board.have_player_position(msg.idnum):

          if board.set_player_start_position(msg.idnum, msg.x, msg.y, msg.position):
            # check for token movement
            positionupdates, eliminated = board.do_player_movement(live_idnums)
            #print(live_idnums)

            for msg in positionupdates:
              for i in range(len(player_list)):
                player_list[i].conn.send(msg.pack())
              for i in range(len(spectator_list)):
                spectator_list[i].conn.send(msg.pack())

            playerid.pop(0)
            playerid.append(idnum)
            
            for j in eliminated:
            
              for i in range(len(player_list)):
                player_list[i].conn.send(tiles.MessagePlayerEliminated(j).pack())
              playerid.remove(j)
              for i in range(len(spectator_list)):
                spectator_list[i].conn.send(tiles.MessagePlayerEliminated(j).pack())
              #return
            
            if not playerid:
              break
            
            # start next turn
            
          
           
            for i in range(len(player_list)):
                player_list[i].conn.send(tiles.MessagePlayerTurn(playerid[0]).pack())
            for i in range(len(spectator_list)):
              spectator_list[i].conn.send(tiles.MessagePlayerTurn(playerid[0]).pack())
      
      
# create a TCP/IP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# listen on all network interfaces
server_address = ('', 30020)
sock.bind(server_address)

print('listening on {}'.format(sock.getsockname()))

sock.listen(5)

while True:
  # handle each new connection independently
  
  connection, client_address = sock.accept()
  print('received connection from {}'.format(client_address))
  player_no+=1
  number_of_connections+=1
  thread= threading.Thread(target=client_handler,args=(connection,client_address,player_no,),daemon=True)
  thread_pool.append(thread)
  # Start immediately when 2 clients connect
  if number_of_connections>=2 and gameStart==False:
    for i in thread_pool:
      i.start()
    gameStart = True #Game alr start so set to true
  elif number_of_connections>=2 and gameStart==True:
    spectator_thread = threading.Thread(target=client_handler,args=(connection,client_address,player_no,),daemon=True)
    spectator_thread.start()
  # >2 clients will be send to be spectators and can join to play actively when the game resets/ends


      
    
    
    
