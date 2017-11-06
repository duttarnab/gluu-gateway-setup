#!/usr/bin/python

import subprocess
import traceback
import time
import os
import sys
import socket
import psycopg2
import random
import string
import shutil
import requests
import json


from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


class KongSetup(object):
    def __init__(self):
        self.hostname = ''
        self.ip = ''

        self.installPostgress = True
        self.installRedis = True
        self.installOxd = True

        self.cert_folder = './certs'
        self.template_folder = './templates'
        self.output_folder = './output'
        self.system_folder = './system'
        self.osDefault = '/etc/default'

        self.logError = 'oxd-kong-setup_error.log'
        self.log = 'oxd-kong-setup.log'

        self.kongConfigFile = '/etc/kong/kong.conf'
        self.kongCustomPlugins = 'kong-uma-rs'

        self.oxdLicense = ''

        self.kongSslCert = ''
        self.kongSslKey = ''
        self.templates = {'/etc/kong/kong.conf': True}
        self.pgPwd = ''

        self.cmd_mkdir = '/bin/mkdir'
        self.opensslCommand = '/usr/bin/openssl'
        self.cmd_chown = '/bin/chown'
        self.cmd_chmod = '/bin/chmod'
        self.cmd_ln = '/bin/ln'
        self.hostname = '/bin/hostname'

        self.countryCode = ''
        self.state = ''
        self.city = ''
        self.orgName = ''
        self.admin_email = ''

        self.distFolder = '/opt'
        self.distKongGUIFolder = '%s/kongGUI' % self.distFolder
        self.distKongAPIGatewayFolder = '%s/kongAPIGateway' % self.distFolder
        self.distKongAPIConfigFile = '%s/.env-dev' % self.distKongAPIGatewayFolder

        self.kongGUIService = "kong-gui"
        self.kongAPIGatewayService = "kong-api"

        # kong API Property values
        self.apiPort = '4040'
        self.apiURL = 'https://%s' % self.run([self.hostname])
        self.apiJwtExpireTime = '24h'
        self.apiAppSecret = self.getPW()
        self.apiLdapMaxConn = 10
        self.apiLdapHost = ''
        self.apiLdapBindDN = 'cn=directory manager,o=gluu'
        self.apiLdapPassword = ''
        self.apiLdapLogLevel = 'debug'
        self.apiLdapClientId = ''
        self.apiPolicyType = 'uma_rpt_policy'
        self.apiOxdId = ''
        self.apiOP = ''
        self.apiClientId = ''
        self.apiClientSecret = ''
        self.apiOxdWeb = ''
        self.apiKongWebURL = ''

    def configureRedis(self):
        return True

    def configurePostgres(self):
        con = None
        try:
            pgPassword = self.getPrompt('Enter postgres password')
            self.pgPwd = self.getPrompt('Enter new kong user password')
            con = psycopg2.connect("host='localhost' dbname='postgres' user='postgres' password='%s'" % pgPassword)
            con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cur = con.cursor()
            cur.execute("CREATE USER kong")
            cur.execute("ALTER USER kong WITH PASSWORD '%s'" % self.pgPwd)
            cur.execute("CREATE DATABASE kong OWNER kong")
            con.commit()
        except psycopg2.DatabaseError, e:
            if con:
                con.rollback()
            self.logIt('Error %s' % e)
        finally:
            if con:
                con.close()

    def configureOxd(self):
        return True

    def detect_hostname(self):
        detectedHostname = None
        try:
            detectedHostname = socket.gethostbyaddr(socket.gethostname())[0]
        except:
            try:
                detectedHostname = os.popen("/bin/hostname").read().strip()
            except:
                self.logIt("No detected hostname", True)
                self.logIt(traceback.format_exc(), True)
        return detectedHostname

    def getExternalCassandraInfo(self):
        return True

    def getExternalOxdInfo(self):
        return True

    def getExternalPostgressInfo(self):
        return True

    def getExternalRedisInfo(self):
        return True

    def gen_cert(self, serviceName, password, user='root', cn=None):
        self.logIt('Generating Certificate for %s' % serviceName)
        key_with_password = '%s/%s.key.orig' % (self.cert_folder, serviceName)
        key = '%s/%s.key' % (self.cert_folder, serviceName)
        csr = '%s/%s.csr' % (self.cert_folder, serviceName)
        public_certificate = '%s/%s.crt' % (self.cert_folder, serviceName)
        self.run([self.opensslCommand,
                  'genrsa',
                  '-des3',
                  '-out',
                  key_with_password,
                  '-passout',
                  'pass:%s' % password,
                  '2048'
                  ])
        self.run([self.opensslCommand,
                  'rsa',
                  '-in',
                  key_with_password,
                  '-passin',
                  'pass:%s' % password,
                  '-out',
                  key
                  ])

        certCn = cn
        if certCn == None:
            certCn = self.hostname

        self.run([self.opensslCommand,
                  'req',
                  '-new',
                  '-key',
                  key,
                  '-out',
                  csr,
                  '-subj',
                  '/C=%s/ST=%s/L=%s/O=%s/CN=%s/emailAddress=%s' % (
                      self.countryCode, self.state, self.city, self.orgName, certCn, self.admin_email)
                  ])
        self.run([self.opensslCommand,
                  'x509',
                  '-req',
                  '-days',
                  '365',
                  '-in',
                  csr,
                  '-signkey',
                  key,
                  '-out',
                  public_certificate
                  ])
        self.run([self.cmd_chown, '%s:%s' % (user, user), key_with_password])
        self.run([self.cmd_chmod, '700', key_with_password])
        self.run([self.cmd_chown, '%s:%s' % (user, user), key])
        self.run([self.cmd_chmod, '700', key])

    def getPW(self, size=12, chars=string.ascii_uppercase + string.digits + string.lowercase):
        return ''.join(random.choice(chars) for _ in range(size))

    def genKongSslCertificate(self):
        self.gen_cert('oxd-kong', self.getPW())
        self.kongSslCert = os.path.join(self.cert_folder, 'oxd-kong.crt')
        self.kongSslKey = os.path.join(self.cert_folder, 'oxd-kong.key')

    def get_ip(self):
        testIP = None
        detectedIP = None
        try:
            testSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            detectedIP = [(testSocket.connect(('8.8.8.8', 80)),
                           testSocket.getsockname()[0],
                           testSocket.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]
        except:
            self.logIt("No detected IP address", True)
            self.logIt(traceback.format_exc(), True)
        if detectedIP:
            testIP = self.getPrompt("Enter IP Address", detectedIP)
        else:
            testIP = self.getPrompt("Enter IP Address")
        if not self.isIP(testIP):
            testIP = None
            print 'ERROR: The IP Address is invalid. Try again\n'
        return testIP

    def getPrompt(self, prompt, defaultValue=None):
        try:
            if defaultValue:
                user_input = raw_input("%s [%s] : " % (prompt, defaultValue)).strip()
                if user_input == '':
                    return defaultValue
                else:
                    return user_input
            else:
                input = False
                while not input:
                    user_input = raw_input("%s : " % prompt).strip()
                    if user_input != '':
                        input = True
                        return user_input
        except KeyboardInterrupt:
            sys.exit()
        except:
            return None

    def installSample(self):
        return True

    def configKongGUI(self):
        self.run(['sudo', 'npm', 'install', '-P'], self.distKongGUIFolder, os.environ.copy(), True)
        self.run(['sudo', 'bower', 'install', '--allow-root'], self.distKongGUIFolder, os.environ.copy(), True)

    def configKongAPIGateway(self):
        self.run(['sudo', 'npm', 'install', '-P'], self.distKongAPIGatewayFolder, os.environ.copy(), True)
        print 'The next few questions are used to configure kong API Gateway'
        self.apiOP = self.getPrompt('OP host')
        self.apiLdapPassword = self.getPrompt('LDAP password')
        self.apiLdapClientId = self.getPrompt('LDAP client id')
        self.apiOxdWeb = self.getPrompt('oxd-https URL')
        flag = self.makeBoolean(self.getPrompt('Would you like to generate client_id/client_secret? (yes - generate, no - enter client_id and client_secret manually)'))
        if flag:
            payload = {
                'op_host': self.apiOP,
                'authorization_redirect_uri': 'https://' + self.hostname + '/login.html',
                'scope': ['openid', 'email', 'profile', 'uma_protection'],
                'grant_types': ['authorization_code'],
                'client_name': 'oxd_kong_client'
            }
            res = requests.post(self.apiOxdWeb + '/setup-client', data=json.dumps(payload), headers = {'content-type': 'application/json'})
            resJson = json.loads(res.text)
            print resJson
            print 'Making client...'
            self.apiClientSecret = resJson['data']['client_secret']
            self.apiClientId = resJson['data']['client_id']
        else:
            self.apiClientId = self.getPrompt('client_id')
            self.apiClientSecret = self.getPrompt('client_secret')

        self.apiKongWebURL = self.getPrompt('Kong Web URL')
        # Render kongAPI property
        self.renderTemplateInOut(self.distKongAPIConfigFile, self.template_folder, self.distKongAPIGatewayFolder)



    def isIP(self, address):
        try:
            socket.inet_aton(address)
            return True
        except socket.error:
            return False

    def logIt(self, msg, errorLog=False):
        if errorLog:
            f = open(self.logError, 'a')
            f.write('%s %s\n' % (time.strftime('%X %x'), msg))
            f.close()
        f = open(self.log, 'a')
        f.write('%s %s\n' % (time.strftime('%X %x'), msg))
        f.close()

    def makeBoolean(self, c):
        if c in ['t', 'T', 'y', 'Y']:
            return True
        if c in ['f', 'F', 'n', 'N']:
            return False
        self.logIt("makeBoolean: invalid value for true|false: " + c, True)

    def makeFolders(self):
        try:
            self.run([self.cmd_mkdir, '-p', self.cert_folder])
            self.run([self.cmd_mkdir, '-p', self.output_folder])
        except:
            self.logIt("Error making folders", True)
            self.logIt(traceback.format_exc(), True)

    def promptForProperties(self):
        self.ip = self.get_ip()
        self.hostname = self.getPrompt('Enter Kong hostname', self.detect_hostname())
        print 'The next few questions are used to generate the Kong self-signed certificate'
        self.countryCode = self.getPrompt('Country')
        self.state = self.getPrompt('State')
        self.city = self.getPrompt('City')
        self.orgName = self.getPrompt('Organizatoin')
        self.admin_email = self.getPrompt('email')
        print 'The next few questions will determine which components are installed'
        self.installOxd = self.makeBoolean(self.getPrompt("Install oxd?", "True")[0])
        self.installPostgress = self.makeBoolean(self.getPrompt("Install Postgress?", "True")[0])
        self.installRedis = self.makeBoolean(self.getPrompt("Install Redis?", "True")[0])
        if not self.installOxd:
            self.getExternalOxdInfo()
        if not self.installRedis:
            self.getExternalRedisInfo()
        if not self.installPostgress:
            externalPostgress = self.makeBoolean(self.getPrompt("Configfure External Postgress?", "True")[0])
            if externalPostgress:
                self.getExternalPostgressInfo()
            else:
                print "Defaulting to external Cassandra"
                self.getExternalCassandraInfo()

    def render_templates(self):
        self.logIt("Rendering templates")
        # other property
        for filePath in self.templates.keys():
            try:
                self.renderTemplate(filePath)
            except:
                self.logIt("Error writing template %s" % filePath, True)
                self.logIt(traceback.format_exc(), True)

    def renderTemplate(self, filePath):
        self.renderTemplateInOut(filePath, self.template_folder, self.output_folder)

    def renderTemplateInOut(self, filePath, templateFolder, outputFolder):
        self.logIt("Rendering template %s" % filePath)
        fn = os.path.split(filePath)[-1]
        f = open(os.path.join(templateFolder, fn))
        template_text = f.read()
        f.close()
        newFn = open(os.path.join(outputFolder, fn), 'w+')
        newFn.write(template_text % self.__dict__)
        newFn.close()

    def run(self, args, cwd=None, env=None, usewait=False):
        self.logIt('Running: %s' % ' '.join(args))
        try:
            p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, env=env)
            if usewait:
                code = p.wait()
                self.logIt('Run: %s with result code: %d' % (' '.join(args), code))
            else:
                output, err = p.communicate()
                if output:
                    self.logIt(output)
                if err:
                    self.logIt(err, True)
        except:
            self.logIt("Error running command : %s" % " ".join(args), True)
            self.logIt(traceback.format_exc(), True)

    def startKong(self):
        self.run(["sudo", "kong", "start", os.path.join(self.output_folder, 'kong.conf')])

    def stopKong(self):
        self.run(["sudo", "kong", "stop"])

    def migrateKong(self):
        self.run(["sudo", "kong", "migrations", "up"])

    def installKongGUIService(self):
        self.logIt("Installing node service %s..." % self.kongGUIService)

        self.copyFile(os.path.join(self.template_folder, self.kongGUIService), self.osDefault)
        self.run([self.cmd_chown, 'root:root', '%s/%s' % (self.osDefault, self.kongGUIService)])

        self.run([
            self.cmd_ln,
            '-sf',
            os.path.join(self.system_folder, self.kongGUIService),
            '/etc/init.d/%s' % self.kongGUIService])

    def installKongAPIService(self):
        self.logIt("Installing kong API service %s..." % self.kongAPIGatewayService)

        self.copyFile(os.path.join(self.template_folder, self.kongAPIGatewayService), self.osDefault)
        self.run([self.cmd_chown, 'root:root', '%s/%s' % (self.osDefault, self.kongAPIGatewayService)])

        self.run([
            self.cmd_ln,
            '-sf',
            os.path.join(self.system_folder, self.kongAPIGatewayService),
            '/etc/init.d/%s' % self.kongAPIGatewayService])

    def copyFile(self, inFile, destFolder):
        try:
            shutil.copy(inFile, destFolder)
            self.logIt("Copied %s to %s" % (inFile, destFolder))
        except:
            self.logIt("Error copying %s to %s" % (inFile, destFolder), True)
            self.logIt(traceback.format_exc(), True)

    def test(self):
        r = requests.get("https://jsonplaceholder.typicode.com/posts")
        print json.loads(r.text)[0]['id']


if __name__ == "__main__":
    kongSetup = KongSetup()
    try:
        # kongSetup.test()
        kongSetup.makeFolders()
        kongSetup.promptForProperties()
        kongSetup.configKongAPIGateway()
        # kongSetup.configureRedis()
        # kongSetup.configurePostgres()
        # kongSetup.configureOxd()
        # kongSetup.genKongSslCertificate()
        # kongSetup.render_templates()
        # kongSetup.stopKong()
        # kongSetup.migrateKong()
        # kongSetup.startKong()
        # kongSetup.installKongGUIService()
        # kongSetup.installSample()
        # kongSetup.test()
        # print "\n\n  oxd Kong installation successful! Point your browser to https://%s\n\n" % kongSetup.hostname
    except:
        kongSetup.logIt("***** Error caught in main loop *****", True)
        kongSetup.logIt(traceback.format_exc(), True)
        print "Installation failed. See: \n  %s \n  %s \nfor more details." % (kongSetup.log, kongSetup.logError)