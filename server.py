import os
from flask import Flask, request, make_response, redirect, render_template, url_for, flash
from flask import send_from_directory
import swiftclient.client as swiftclient
import keystoneclient.v3 as keystoneclient
import json
import pyDes

# Initializing flask app
app = Flask(__name__)

# Bluemix VCAP services
PORT = int(os.getenv('VCAP_APP_PORT', 8080))

# Bluemix object storage name
objectstore_container_name = 'cfstorage'

# Bluemix credentials for connecting to object storage service
bluemix_credential = json.loads(os.environ['VCAP_SERVICES'])['Object-Storage'][0]
objectstore = bluemix_credential['credentials']
conn = swiftclient.Connection(key=objectstore['password'],
                              authurl=objectstore['auth_url'] + '/v3',
                              auth_version='3',
                              os_options={"project_id": objectstore['projectId'],
                                          "user_id": objectstore['userId'],
                                          "region_name": objectstore['region']})

# create a default container
def containercheck():
    for container in conn.get_account()[1]:
        print container['name']
        return False
    conn.put_container(objectstore_container_name)
    return True


# Returns the lis of files in the specific container
def fileList():
    listoffiles = []
    list = {}
    iterator = 0
    for container in conn.get_account()[1]:
        for content in conn.get_container(container['name'])[1]:
            list['f' + str(iterator)] = 'File Name: {0} \t\t File Size: {1} \t\t Last modified at: {2}'.format(
                content['name'], content['bytes'], content['last_modified'])
            listoffiles.append(list)
            iterator += 1
    return listoffiles


@app.route('/')
def index():
    list1 = fileList()
    return render_template('index.html', uploadstatus='2', filelist=list1)


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    containercheck()
    file = request.files['file']
    fcontent = file.read()
    flength = len(fcontent)
    totalContainerSize = 0
    for container in conn.get_account()[1]:
        for data in conn.get_container(container['name'])[1]:
            totalContainerSize += data['bytes']

    # totalContainerSize is the size of all the files in the specified container on object storage
    if totalContainerSize < 10000000:
        if flength < 1000000:
            # pyDes encryption key generation
            encryption_key = pyDes.des("DESCRYPT", pyDes.CBC, "\0\0\0\0\0\0\0\0", pad=None, padmode=pyDes.PAD_PKCS5)
            # encrypt contents of the file using pyDes library
            encrypted_data = encryption_key.encrypt(fcontent)
            # write encrypted contents to a file
            with open(file.filename, 'w') as local_file:
                conn.put_object(objectstore_container_name,
                                file.filename,
                                contents=encrypted_data,
                                content_type='text/plain')
        else:
            list1 = fileList()
            return render_template('index.html', uploadstatus='0', filelist=list1)
    else:
        list1 = fileList()
        return render_template('index.html', uploadstatus='0', filelist=list1)

    list1 = fileList()
    return render_template('index.html', uploadstatus='1', filelist=list1)


@app.route('/deletefile/<fname>', methods=['GET', 'POST'])
def deleteFile(fname):
    try:
        # delete specified filr from the specified container
        conn.delete_object(objectstore_container_name, fname)
    except:
        return 'False'
    return 'True'


@app.route('/downloadFile', methods=['GET', 'POST'])
def downloadFile():
    try:
        filename = request.form['filename']
        file_name = filename.strip()
        # pyDes decryption key
        decryption_key = pyDes.des("DESCRYPT", pyDes.CBC, "\0\0\0\0\0\0\0\0", pad=None, padmode=pyDes.PAD_PKCS5)
        object = conn.get_object(objectstore_container_name, file_name)
        # write decrypted object to file
        with open(file_name, 'w') as local_file:
            local_file.write(decryption_key.decrypt(object[1]))
    except:
        return 'Incorrect Name'
    # return the file to the browser so that it can be downloaded by the user.
    response = make_response(str(decryption_key.decrypt(object[1])))
    response.headers["Content-Disposition"] = "attachment; filename=" + file_name
    # return file as a response
    return response

# start flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
