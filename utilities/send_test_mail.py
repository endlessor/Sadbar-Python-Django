import smtplib
import argparse
import time
start_time = time.time()

parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('server', metavar='Server', nargs='+', default=['google',
                                                                    'xander'],
                    help='Must be "google" or "xander"')
args = parser.parse_args()

msg = 'Test message'
you = 'xander.sereda@gmail.com'

try:
    if args.server[0] == 'google':
        me = 'den.s.work2@gmail.com'
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login("den.s.work2@gmail.com", "1qaz2w3e4r")
        server.sendmail(me, [you], msg)
        server.quit()
        print("Success! Elapsed time: %s" % (time.time() - start_time))
    elif args.server[0] == 'xander':
        me = 'xander@netspark.io'
        server = smtplib.SMTP('mail.privateemail.com', 26)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login("xander@netspark.io", "!D3QY8oA7axQK")
        server.sendmail(me, [you], msg)
        server.quit()
        print("Success! Elapsed time: %s" % (time.time() - start_time))
    else:
        print 'Must be "google" or "xander" args!'
except Exception as e:
    print 'Error: %s' % e