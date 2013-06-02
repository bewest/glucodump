#!/usr/bin/python
import sys, os
import select, socket

import usbcomm
import usb

_default_host = 'localhost'
_default_port = 23200

_READ_ONLY = select.POLLIN | select.POLLPRI

class Stream(object):
  def __init__(self,
        host=_default_host,
        port=_default_port):

    self.host = host
    self.port = port
    self.usb = usbcomm.USBComm(idVendor=usbcomm.ids.Bayer, idProduct=usbcomm.ids.Bayer.Contour)

    self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.server.setblocking(0)

    self.poller = select.poll()

    self.fd_to_socket = {}
    self.clients = []

  def close(self):
    print >>sys.stderr, '\nMUX > Closing...'

    for client in self.clients:
      client.close()
    self.usb.close()
    self.server.close()

    print >>sys.stderr, 'MUX > Done! =)'

  def add_client(self, client):
    print >>sys.stderr, 'MUX > New connection from', client.getpeername()
    client.setblocking(0)
    self.fd_to_socket[client.fileno()] = client
    self.clients.append(client)
    self.poller.register(client, _READ_ONLY)

  def remove_client(self, client, why='?'):
    try:
      name = client.getpeername()
    except:
      name = 'client %d' % client.fileno()
    print >>sys.stderr, 'MUX > Closing %s: %s' % (name, why)
    self.poller.unregister(client)
    self.clients.remove(client)
    client.close()

  def read(self):
    self.sink = None
    try:
      data = self.usb.read( )
      self.sink = data
    except usb.core.USBError, e:
      if e.errno != 110:
        print e, dir(e), e.backend_error_code, e.errno
        raise
    return self.sink is not None

  def flush(self):
    if self.sink is not None:
      for client in self.clients:
        client.send(self.sink)
    self.sink = None

  def run(self):
    try:
      # self.tty.setTimeout(0) # Non-blocking
      # self.tty.flushInput()
      # self.tty.flushOutput()
      # self.poller.register(self.usb.epout.bEndpointAddress, _READ_ONLY)
      # self.fd_to_socket[self.usb.epout.bEndpointAddress] = self.usb
      # print >>sys.stderr, 'MUX > Serial port: %s @ %s' % (self.device, self.baudrate)
      print >>sys.stderr, 'MUX > usb port: %s' % (self.usb)

      self.server.bind((self.host, self.port))
      self.server.listen(5)
      self.poller.register(self.server, _READ_ONLY)
      self.fd_to_socket[self.server.fileno()] = self.server
      print >>sys.stderr, 'MUX > Server: %s:%d' % self.server.getsockname()

      print >>sys.stderr, 'MUX > Use ctrl+c to stop...\n'

      while True:
        events = self.poller.poll(500)
        if self.read( ):
          self.flush( )
          
        for fd, flag in events:
          # Get socket from fd
          s = self.fd_to_socket[fd]
          print fd, flag, s

          if flag & select.POLLHUP:
            self.remove_client(s, 'HUP')

          elif flag & select.POLLERR:
            self.remove_client(s, 'Received error')

          elif flag & (_READ_ONLY):
            # A readable server socket is ready to accept a connection
            if s is self.server:
              connection, client_address = s.accept()
              self.add_client(connection)

            # Data from serial port
            elif s is self.usb:
              data = s.read( )
              for client in self.clients:
                client.send(data)

            # Data from client
            else:
              data = s.recv(80)

              # Client has data
              print "send to usb"
              if data: self.usb.write(data)

              # Interpret empty result as closed connection
              else: self.remove_client(s, 'Got no data')

    except usb.core.USBError, e:
      print >>sys.stderr, '\nMUX > USB error: "%s". Closing...' % e

    except socket.error, e:
      print >>sys.stderr, '\nMUX > Socket error: %s' % e.strerror

    except (KeyboardInterrupt, SystemExit):
      pass

    finally:
      self.close()

if __name__ == '__main__':
  s = Stream( )
  s.run( )
