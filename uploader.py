# Copyright (C) 2017 - Chenfeng Bao
#
# This program is free software; you can redistribute it and/or modify it 
# under the terms of the GNU General Public License; either version 3 of 
# the License, or (at your option) any later version.
# You should have received a copy of the GNU General Public License 
# along with this program; if not, see <http://www.gnu.org/licenses>.

#forked from cleaner. This is a script to be called from the command line to upload files
#and give a sharable link

import httplib2
import os
import sys
import argparse
import time
import calendar
import logging
import warnings

from apiclient import discovery
from apiclient.errors import HttpError
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
from apiclient.http import MediaFileUpload

if getattr(sys, 'frozen', False):
    # running in a bundle
    CLEANER_PATH = sys.executable
else:
    # running as a normal Python script
    CLEANER_PATH = os.path.realpath(__file__)
PAGE_TOKEN_FILE = os.path.join(os.path.dirname(CLEANER_PATH), 'page_token')
CREDENTIAL_FILE = os.path.join(os.path.expanduser('~'), '.credentials', 'google-drive-trash-cleaner.json')

CLIENT_CREDENTIAL = {
    "client_id" : "359188752904-817oqa6dr7elufur5no09q585trpqf1l.apps.googleusercontent.com",
    "client_secret" : "uZtsDf5vaUm8K-kZLZETmsYi",
    "scope" : 'https://www.googleapis.com/auth/drive',
    "redirect_uri" : "urn:ietf:wg:oauth:2.0:oob",
    "token_uri" : "https://accounts.google.com/o/oauth2/token",
    "auth_uri" : "https://accounts.google.com/o/oauth2/auth",
    "revoke_uri" : "https://accounts.google.com/o/oauth2/revoke",
    "pkce" : True
}

PAGE_SIZE_LARGE = 1000
PAGE_SIZE_SMALL = 100
PAGE_SIZE_SWITCH_THRESHOLD = 3000
RETRY_NUM = 3
RETRY_INTERVAL = 2
TIMEOUT_DEFAULT = 300

class TimeoutError(Exception):
    pass

class PageTokenFile:
    def __init__(self, filePath):
        self.path = filePath
    
    def get(self):
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                pageToken = int(f.read())
        except (FileNotFoundError, ValueError):
            pageToken = 0
        return pageToken
    
    def save(self, pageToken):
        with open(self.path, 'w', encoding='utf-8') as f:
            f.write(str(pageToken))

def main():
    flags = parse_cmdline()
    logger = configure_logs(flags.logfile)
    pageTokenFile = PageTokenFile(flags.ptokenfile)
    for i in range(RETRY_NUM):
        try:
            service = build_service(flags)
            pageToken = pageTokenFile.get()
            
            if not sys.argv[1]:
                print('no arguent given')
            
            #print(upload_file(service,'uploader.py'))
            
            else:
                make_folder_upload_share(service,sys.argv[1])
        except client.HttpAccessTokenRefreshError:
            print('Authentication error')
        except httplib2.ServerNotFoundError as e:
            print('Error:', e)
        except TimeoutError:
            print('Timeout: Google backend error.')
            print('Retries unsuccessful. Abort action.')
            return
        else:
            break
        time.sleep(RETRY_INTERVAL)
    else:
        print("Retries unsuccessful. Abort action.")
        return
    
    
     
        
def make_folder_upload_share(service,foldername):
    #takes a given folder on local system (foldername)
    #and then creates a folder on Google Drive with said name
    #and then uploads all files in that folder
    
    if not os.path.isdir(foldername):
        return 0
    else:
        print('foldername is a proper folder')
    
    #get realpath
    foldername = os.path.realpath(foldername)
    print('Taking files from ',foldername)


    #create that folder in google drive
    parentID = create_folder(service,os.path.basename(foldername))
    print('Creating folder with name ',os.path.basename(foldername))
    
    files = os.listdir(foldername)
    
    #change directory to make copying easier
    os.chdir(foldername)
    
    fileIDs = []
    
    for file in files:
        if os.path.isfile(file): #currently runs error when there are directories
            fileIDs.append(upload_file(service,file,parentID))
        else:
            print('skipping directory',file)
        
    #share folder for those with a link 
    share_with_link(service,parentID)
    
    return
        
        
def share_with_link(service,file_id):
    def callback(request_id, response, exception):
        if exception:
            # Handle error
            print(exception)
        else:
            print(response.get('id'))
            
    batch = service.new_batch_http_request(callback=callback)
    user_permission = {
        #"kind": "drive#permission",
        #"id": "anyoneWithLink",
        "type": "anyone",
        "role": "reader",
    }
    batch.add(service.permissions().create(
        fileId=file_id,
        body=user_permission,
        fields='id',
    ))
    batch.execute()
    
    print('\nGet your files at the link below')
    print('https://drive.google.com/drive/folders/'+file_id+'?usp=sharing')
    
    return

    
    
        
def create_folder(service,foldername):
    
    #creates folder, returns parent id
    file_metadata = {
    'name': foldername,
    'mimeType': 'application/vnd.google-apps.folder'
    }
    file = service.files().create(body=file_metadata,
                                    fields='id').execute()
    
    
    print ('Folder ID: %s' % file.get('id'))
    return file.get('id')

    
    
        
def upload_file(service,uploadfile,parentID):
    ##https://developers.google.com/drive/v3/web/manage-uploads
        
    file_metadata = {'name': uploadfile}
    
    if parentID:
        file_metadata['parents'] = [parentID]
    
    #result = service.files().insert(convert=False, body=file_metadata,
    #        media_body=filebasename, fields='mimeType,exportLinks').execute()
    
    #media = MediaFileUpload(uploadfile,mimetype='text/plain')
    media = MediaFileUpload(uploadfile)


    
    result = service.files().create(body=file_metadata,
                                    media_body=media,
                                    fields='id').execute()

    
    if result:
        print('Uploaded' ,uploadfile,'as', result.get('id'))
    
    #print 'File ID: %s' % file.get('id')
    return result


def untrash_files(service,matchstring):
    f = open('finalfile.csv','r')
    
    for line in f.readlines():
        fid = line.split(',')[0]
        #print(fid,line.split(',')[1][:-1],matchstring)
        
        if matchstring in line.split(',')[1][:-1]:
            print(fid, line.split(',')[1])
            #untrash
            #files.update with {'trashed':false}
            service.files().update(fileId=fid,body={'trashed':False},fields='id, modifiedTime').execute()



def get_parent_name(service):
    f = open('myfile.csv', 'r')
    g = open('finalfile.csv','w')
    abc = 1
    for line in f.readlines():
        abc = abc+1
        fid = line.split(',')[0]
        print(line.split(',')[2][-5:-1])
        if 'png' not in line.split(',')[2] :
            if '.' in line.split(',')[2][-7:]:
                print(fid,abc)
                parents = service.files().get(fileId=fid,fields='parents').execute()
            
                parentname = service.files().get(fileId=parents['parents'][0],fields='name').execute()
            
                g.write(fid+','+parentname['name']+'\n')
                print(fid+','+parentname['name'])
        
    f.close()
    return
        

def parse_cmdline():
    flags = argparse.Namespace(auth_host_name='localhost', auth_host_port=[8080, 8090], auto=False, credfile='/home/brian/.credentials/google-drive-trash-cleaner.json', days=30, fullpath=False, logfile=None, logging_level='ERROR', mydriveonly=False, noauth_local_webserver=False, noprogress=False, ptokenfile='/home/brian/python/cleaner/google-drive-trash-cleaner-master/page_token', quiet=False, timeout=300, view=False)
    return flags

def configure_logs(logPath):
    logger = logging.getLogger('gdtc')
    logger.setLevel(logging.INFO)
    if not logPath:
        return logger
    logPath = logPath.strip('"')
    open(logPath, 'a').close()
    fileHandler = logging.FileHandler(
        logPath, mode='a', encoding='utf-8')
    logger.addHandler(fileHandler)
    return logger

def build_service(flags):
    credentials = get_credentials(flags)
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v3', http=http)
    return service

def get_credentials(flags):
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    store = Storage(flags.credfile)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.OAuth2WebServerFlow(**CLIENT_CREDENTIAL)
        credentials = tools.run_flow(flow, store, flags)
        print('credential file saved at\n\t' + flags.credfile)
    return credentials

def get_deletion_list(service, pageToken, flags, pathFinder=None):
    """Get list of files to be deleted and page token for future use.
    
    deletionList, pageTokenBefore, pageTokenAfter
        = get_deletion_list(service, pageToken, maxTrashDays, timeout)
    
    Iterate through Google Drive change list to find trashed files in order 
    of trash time. Return a list of files trashed more than maxTrashDays 
    seconds ago and a new page token for future use.
    
    service:        Google API service object
    pageToken:      An integer referencing a position in Drive change list.
                    Only changes made after this point will be checked. By 
                    assumption, trashed files before this point are all 
                    deleted.
    deletionList:   List of trashed files to be deleted, in ascending order of 
                    trash time. Each file is represented as a dictionary with 
                    keys {'fileId', 'time', 'name'}.
    flags:          Flags parsed from command line. Should contain the 
                    following attributes:
                    --noprogress    don't show scanning progress
                    --fullpath      show full path
                    --mydriveonly   restrict to my drive
                    --quiet         don't show individual file info
                    --timeout       timeout in seconds
                    --days          maximum days in trash
    pageTokenBefore:
                    An integer representing a point in Drive change list, 
                    >= 'pageToken'.
                    This page token is before everything in deletionList. Can 
                    be used as future pageToken no matter what.
    pageTokenAfter: An integer representing a point in Drive change list, 
                    >= 'pageToken'.
                    Can be used as future pageToken only if everything in 
                    deletionList is deleted.
    """
    
    print('running deletionlist')
    f = open('myfile.csv', 'w')
    response = execute_request(service.changes().getStartPageToken(), flags.timeout)
    latestPageToken = int(response.get('startPageToken'))
    currentTime = time.time()
    deletionList = []
    if not pageToken:
        pageToken = 1
    pageTokenBefore = pageToken
    pageSize = PAGE_SIZE_LARGE
    progress = ScanProgress(quiet=flags.quiet, noProgress=flags.noprogress)
    if not pathFinder and flags.fullpath:
        pathFinder = PathFinder(service)
    while pageToken:
        if latestPageToken - int(pageToken) < PAGE_SIZE_SWITCH_THRESHOLD:
            pageSize = PAGE_SIZE_SMALL
        request = service.changes().list(
                    pageToken=pageToken, includeRemoved=False,
                    pageSize=pageSize, restrictToMyDrive=flags.mydriveonly,
                    fields='nextPageToken,newStartPageToken,'
                    'changes(fileId,time,file(name,parents,explicitlyTrashed,ownedByMe))'
                    )
        response = execute_request(request, flags.timeout)
        items = response.get('changes', [])
        for item in items:
            itemTime = parse_time(item['time'])
            if currentTime - itemTime < flags.days*24*3600:
                progress.clear_line()
                return deletionList, pageTokenBefore, pageToken
            progress.print_time(item['time'])
            if item['file']['explicitlyTrashed'] and item['file']['ownedByMe']:
                if flags.fullpath:
                    disp = pathFinder.get_path(item['fileId'], fileRes=item['file'])
                else:
                    disp = item['file']['name']
                progress.found(item['time'], disp)
                f.write(item['fileId']+','+item['time']+','+disp+'\n')  # python will convert \n to os.linesep
                deletionList.append({'fileId': item['fileId'], 'time': item['time'],
                                        'name': disp})
        pageToken = response.get('nextPageToken')
        if not deletionList:
            pageTokenBefore = pageToken
    progress.clear_line()
    
    
    f.close()  # you can omit in most cases as the destructor will call it
    return deletionList, pageTokenBefore, int(response.get('newStartPageToken'))

def print_parents(service, file_id):
  """Print a file's parents.

  Args:
    service: Drive API service instance.
    file_id: ID of the file to print parents for.
  """
  try:
    parents = service.parents().list(fileId=file_id).execute()
    for parent in parents['items']:
      print('File Id: %s' , parent['id'])
  except:
    print('An error occurred: ',sys.exc_info()[0])



def delete_old_files(service, deletionList, flags):
    """Print and delete files in deletionList
    
    listEmpty = delete_old_files(service, deletionList, flags)
    
    service:        Google API service object
    deletionList:   List of trashed files to be deleted, in ascending order of 
                    trash time. Each file is represented as a dictionary with 
                    keys {'fileId', 'time', 'name'}.
    flags:          Flags parsed from command line arguments. In 
                    particular, automatic deletion (no user prompt) and view-
                    only mode (print but don't delete) are supported.
    listEmpty:      Return True if deletionList is either empty on input or 
                    emptied by this function, False otherwise.
    """
    logger = logging.getLogger('gdtc')
    n = len(deletionList)
    if n == 0:
        print('No files to be deleted')
        return True
    if flags.view:
        if n == 1:
            print('{:} file/folder trashed more than {:} days ago'.format(n, flags.days))
        else:
            print('{:} file/folder(s) trashed more than {:} days ago'.format(n, flags.days))
        return False
    if not flags.auto:
        confirmed = ask_usr_confirmation(n)
        if not confirmed:
            return False
    print('Deleting...')
    for item in reversed(deletionList):
        request = service.files().delete(fileId = item['fileId'])
        execute_request(request, flags.timeout)
        logger.info(item['time'] + ''.ljust(4) + item['name'])
    print('Files successfully deleted')
    return True

class ScanProgress:
    def __init__(self, quiet, noProgress):
        self.printed = "0000-00-00"
        self.noItemYet = True
        self.quiet = quiet
        self.noProgress = noProgress
    
    def print_time(self, timeStr):
        """print yyyy-mm-dd only if not yet printed"""
        if self.noProgress:
            return
        ymd = timeStr[:10]
        if ymd > self.printed:
            print('\rScanning files trashed on ' + ymd, end='')
            self.printed = ymd
    
    def found(self, time, name):
        """found an item, print its info"""
        if self.quiet:
            return
        if not self.noProgress:
            print('\r' + ''.ljust(40) + '\r', end='')
        if self.noItemYet:
            print('Date trashed'.ljust(24) + ''.ljust(4) + 'File Name/Path')
            self.noItemYet = False
        print(time + ''.ljust(4) + name)
        if not self.noProgress:
            print('\rScanning files trashed on ' + self.printed, end='')
    
    def clear_line(self):
        print('\r' + ''.ljust(40) + '\r', end='')
        print()

class PathFinder:
    def __init__(self, service, cache=None):
        self.service = service
    # each item in self.cache is a list with 2 elements
    # self.cache[id][0] is the full path of id
    # self.cache[id][1] is the number of times id has been queried
        if cache:
            self.cache = cache
        else:
            self.cache = dict()
    # self.expanded contains all ids that have all their children cached
        self.expanded = set()
    
    def get_path(self, id, fileRes=None):
        """Find the full path for id
        
        fileRes:    File resource for id. 
                    Must have 'name' and 'parents' attributes if available.
                    If None or unspecified, an API call is made to query"""
        if id in self.cache:
            if self.cache[id][1]>1 and id not in self.expanded:
                # find and cache all children if id is requested more than once
                self.expand_cache(id)
            self.cache[id][1] += 1
            return self.cache[id][0]
        if not fileRes:
            request = self.service.files().get(fileId=id, fields='name,parents')
            fileRes = execute_request(request)
        try:
            parentId = fileRes['parents'][0]
            self.cache[id] = [self.get_path(parentId) + os.sep + fileRes['name'], 1]
        except KeyError:
            self.cache[id] = [fileRes['name'], 1]
        return self.cache[id][0]
    
    def expand_cache(self, id):
        if id in self.expanded:
            return
        npt = None
        while True:
            request = self.service.files().list(
                    q="'{:}' in parents and trashed=true".format(id), 
                    pageToken=npt, 
                    fields="files(id,name),nextPageToken",
                    pageSize=1000)
            response = execute_request(request)
            for file in response['files']:
                if file['id'] in self.cache:
                    continue
                self.cache[file['id']] = [self.cache[id][0] + os.sep + file['name'], 0]
            try:
                npt = response['nextPageToken']
            except KeyError:
                break
        self.expanded.add(id)
    
    def clear():
        self.cache.clear()

def execute_request(request, timeout=TIMEOUT_DEFAULT):
    """Execute Google API request
    Automatic retry upon Google backend error (500) until timeout
    """
    while timeout >= 0:
        try:
            response = request.execute()
        except HttpError as e:
            if int(e.args[0]['status']) == 500:
                timeout -= RETRY_INTERVAL
                time.sleep(RETRY_INTERVAL)
                continue
            raise e
        else:
            return response
    raise TimeoutError

def ask_usr_confirmation(n):
    while True:
        if n == 1:
            usrInput = input('Confirm deleting this file/folder? (Y/N)\n')
        else:
            usrInput = input('Confirm deleting these {:} files/folders? (Y/N)\n'.format(n))
        if usrInput.strip().lower() == 'y':
            return True
        elif usrInput.strip().lower() == 'n':
            return False

def parse_time(rfc3339):
    """parse the RfC 3339 time given by Google into Unix time"""
    time_str = rfc3339.split('.')[0]
    return calendar.timegm(time.strptime(time_str, '%Y-%m-%dT%H:%M:%S'))

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nStopped by user')
