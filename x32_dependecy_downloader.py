from bs4 import BeautifulSoup as BS
import os
import subprocess as sp
import re
import requests

try:
    # For Python 3.0 and later
    from urllib.request import urlopen
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib2 import urlopen

# http://cz.archive.ubuntu.com/ubuntu/pool/main/a/alsa-lib/libasound2_1.1.3-5_i386.deb
urlPattern1 = 'https://packages.ubuntu.com/bionic/i386/*/download'
urlPattern2 = 'https://launchpad.net/ubuntu/trusty/i386/*'
arch = ':i386'
linuxDepsPattern = 'dpkg-deb -I * | grep -E --color=none "Depends|Pre\-Depends"'
downloadedDebs = []
failedDebs = []
countSuccess=0
countFailed=0

def findUrl(htmlData, urlText):
    return htmlData.find("a", string=urlText)['href']

def findUrlByRegEx(htmlData, regex):
    return htmlData.find('a', text = re.compile(regex))['href']

def tryFindLibUrl(libName):
    global urlPattern1
    htmlData = fetchHtmlData(constructDownloadUrl(urlPattern1, libName))

    # libs from packages
    try:
        return findUrl(htmlData, 'cz.archive.ubuntu.com/ubuntu')
    except:
        pass
    try:
        return findUrl(htmlData, 'security.ubuntu.com/ubuntu')      
    except:
        pass
    try:
        # Ubuntu 14 libs from launchpad
        global urlPattern2
        htmlDataPage = fetchHtmlData(constructDownloadUrl(urlPattern2, libName))
        return findUrlByRegEx(fetchHtmlData('https://launchpad.net' + findUrlByRegEx(htmlDataPage, 'ubuntu')), '.deb')
    except:
        global countFailed
        countFailed += 1
        failedDebs.append(libName)
        return ''

def constructDownloadUrl(urlPattern, lib):
    return urlPattern.replace('*', lib.split(':')[0])

def fetchHtmlData(downloadUrl):
    print(downloadUrl)
    usock = urlopen(downloadUrl)
    data = usock.read()
    return BS(data, "html.parser")

def resolvePackage(libName):
    # Find download url
    libUrl = tryFindLibUrl(libName)
    print("Download:  " + libName + " from " + libUrl)
    if libUrl == '':
        return False
    global countSuccess
    countSuccess +=1
    # Download deb
    response = requests.get(libUrl)
    debName = libUrl.rsplit('/',1)[1]
    open(debName, 'wb').write(response.content)
    # Get dependencies for deb
    depStr = (''.join(re.split("\(|\)|\[|\]", sp.getoutput(linuxDepsPattern.replace('*', debName)))[::2]))
    # Unpack deb
    os.system('dpkg-deb -x ./'+ debName + ' .')
    downloadedDebs.append(libName)
    # Remove deb
    os.remove(debName) 
    # has deps, pre-deps -> resolve
    if depStr:
        for line in depStr.splitlines():
            depStr = line.split(':')[1].strip()
            if depStr:
                print('Installing dependencies for [', libName , '] :', depStr)
                # skip optionals
                optional = False
                # try other optional if couldn't resolve previous
                tryOther = False
                for dep in depStr.replace(',', '').strip().split(' '):
                    if dep == '|':
                        optional = True
                    elif optional and not tryOther:
                        optional = False
                    elif dep:
                        depName = dep + arch
                        if depName not in downloadedDebs:
                            tryOther = not resolvePackage(depName)
    return True

with open('lotus_notes_9.0.1_deps','r') as f:
    for lib in f.readlines()[0].split():
        resolvePackage(lib)

print('OK count: ', countSuccess)
print('Failed count: ', countFailed)

if len(failedDebs) > 0:
    print('Please install those manualy: ', failedDebs)
    print('  note: missing default-dbus-session-bus:i386 and dbus-session-bus:i386 IS OK :)')
