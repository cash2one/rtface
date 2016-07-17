#!/usr/bin/env python
#
# Cloudlet Infrastructure for Mobile Computing
#
#   Author: Kiryong Ha <krha@cmu.edu>
#
#   Copyright (C) 2011-2013 Carnegie Mellon University
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#

import time
import Queue
import struct
import os
import sys
if os.path.isdir("../gabriel") is True:
    sys.path.insert(0, "..")

from gabriel.proxy.common import AppProxyStreamingClient
from gabriel.proxy.common import AppProxyThread
from gabriel.proxy.common import ResultpublishClient
from gabriel.proxy.common import Protocol_measurement
from gabriel.proxy.common import get_service_list
from gabriel.common.config import ServiceMeta as SERVICE_META
from gabriel.common.config import Const
from face_swap import FaceTransformation

import pdb
from PIL import Image, ImageOps
import io, StringIO
import numpy as np
import json
#from scipy.ndimage import imread
import cProfile, pstats, StringIO
from NetworkProtocol import *
import cv2
from demo_config import Config
from datetime import datetime
from gabriel.common.protocol import Protocol_measurement as Protocol_measurement

prev_timestamp = time.time()*1000


# bad idea to transfer image back using json
class DummyVideoApp(AppProxyThread):

    def gen_response(self, response_type, value):
        msg = {
            'type': response_type,
            'value': value,
            'time': int(time.time()*1000)
            }
        return json.dumps(msg)
        
    
    def process(self, image):
        # preprocessing techqniues : resize?
#        image = cv2.resize(nxt_face, dim, interpolation = cv2.INTER_AREA)

        face_snippets_list = transformer.swap_face(image)
        face_snippets_string = {}
        face_snippets_string['num'] = len(face_snippets_list)
        for idx, face_snippet in enumerate(face_snippets_list):
            face_snippets_string[str(idx)] = face_snippet

        result = json.dumps(face_snippets_string)
        return result

    def handle(self, header, data):
        # pr = cProfile.Profile()
        # pr.enable()
        
        global prev_timestamp
        
        # locking to make sure tracker update thread is not interrupting
        transformer.tracking_thread_idle_event.clear()
        
        if Config.DEBUG:
            cur_timestamp = time.time()*1000
            interval = cur_timestamp - prev_timestamp
            sys.stdout.write("packet interval: %d\n"%interval)
            start = time.time()

        sys.stdout.write('received {}:{}'.format(header['id'], header[Protocol_measurement.JSON_KEY_APP_RECV_TIME]))

        header_dict = header

        if 'reset' in header_dict:
            reset = header_dict['reset']
#            pdb.set_trace()            
            print 'reset openface state'            
            if reset:
#                transformer.terminate()
#                time.sleep(2)
#                transformer = FaceTransformation()
                transformer.openface_client.reset()                
                resp=self.gen_response(AppDataProtocol.TYPE_reset, True)
                transformer.training=False
                return resp

        if 'get_state' in header_dict:
            get_state = header_dict['get_state']
            print 'get openface state'
            sys.stdout.flush()            
            if get_state:
                state_string = transformer.openface_client.getState()
                resp=self.gen_response(AppDataProtocol.TYPE_get_state, state_string)
                print 'send out response {}'.format(resp[:10])
                sys.stdout.flush()
                return resp

        if 'load_state' in header_dict:
            is_load_state = header_dict['load_state']
            if is_load_state:
                sys.stdout.write('loading openface state')
                sys.stdout.write(data[:30])
                sys.stdout.flush()
                state_string = data
                transformer.openface_client.setState(state_string)
                resp=self.gen_response(AppDataProtocol.TYPE_load_state, True)
            else:
                sys.stdout.write('error: has load_state in header, but the value is false')
                resp=self.gen_response(AppDataProtocol.TYPE_load_state, False)
            return resp
            
        if 'remove_person' in header_dict:
            print 'removing person'
            name = header_dict['remove_person']
            remove_success=False
            if isinstance(name, basestring):
                resp=transformer.openface_client.removePerson(name)
                remove_success=json.loads(resp)['val']
                print 'removing person :{} success: {}'.format(name, remove_success)
            else:
                print ('unsupported type for name of a person')
            resp=self.gen_response(AppDataProtocol.TYPE_remove_person, remove_success)
            return resp

        if 'get_person' in header_dict:
            sys.stdout.write('get person\n')
            sys.stdout.flush()
            is_get_person = header_dict['get_person']
            if is_get_person:
                state_string = transformer.openface_client.getPeople()
                resp=self.gen_response(AppDataProtocol.TYPE_get_person, state_string)
                sys.stdout.write('send out response {}\n'.format(resp))
                sys.stdout.flush()
            else:
                sys.stdout.write('error: has get_person in header, but the value is false')
                resp=self.gen_response(AppDataProtocol.TYPE_get_person, False)
            return resp
            
        if 'add_person' in header_dict:
            print 'adding person'
            name = header_dict['add_person']
            if isinstance(name, basestring):
                transformer.addPerson(name)
                transformer.training_cnt = 0                
                print 'training_cnt :{}'.format(transformer.training_cnt)
            else:
                raise TypeError('unsupported type for name of a person')
            resp=self.gen_response(AppDataProtocol.TYPE_add_person, name)
            
        elif 'face_table' in header_dict:
            face_table_string = header_dict['face_table']
            print face_table_string
            face_table = json.loads(face_table_string)
            transformer.face_table=face_table
            for from_person, to_person in face_table.iteritems():
                print 'mapping:'
                print '{0} <-- {1}'.format(from_person, to_person)
            sys.stdout.flush()

        training = False
        if 'training' in header_dict:
            training=True
            name=header_dict['training']

        # using PIL approach to open a jpeg data
        # image_raw = Image.open(io.BytesIO(data))
        # image = np.asarray(image_raw)

        # using opencv imread to open jpeg files
        # hopefully it will hit cache but not memory
        # why not just use imdecode???
        # fake_file = '/tmp/image.jpg'
        # fh=open(fake_file,'wb')
        # fh.write(data)
        # fh.close()
        # bgr_img = cv2.imread(fake_file)
        # b,g,r = cv2.split(bgr_img)       # get b,g,r
        # image = cv2.merge([r,g,b])     # switch it to rgb

        # just pixel data
        data=np.fromstring(data, dtype=np.uint8)
        bgr_img=cv2.imdecode(data,cv2.IMREAD_COLOR)
#        cv2.imwrite('/tmp/bgr_image.jpg', bgr_img)        
        b,g,r = cv2.split(bgr_img)       # get b,g,r
        image = cv2.merge([r,g,b])     # switch it to rgb
#        cv2.imwrite('/tmp/image.jpg', image)
            
        if training:
            cnt, face_json = transformer.train(image, name)
            if face_json is not None:
                msg = {
                    'num': 1,
                    'cnt': cnt,
                    '0': face_json
                }
                msg = json.dumps(msg)
            else:
                # time is a random number to avoid token leak
                msg = {
                    'num': 0,
                    'cnt': cnt,
                }
            resp= self.gen_response(AppDataProtocol.TYPE_train, msg)
        else:
            # swap faces
            snippets = self.process(image)
            resp= self.gen_response(AppDataProtocol.TYPE_detect, snippets)

        if Config.DEBUG:
            end = time.time()
            print('total processing time: {}'.format((end-start)*1000))
            prev_timestamp = time.time()*1000

        transformer.tracking_thread_idle_event.set()

        # pr.disable()
        # s = StringIO.StringIO()
        # sortby = 'cumulative'
        # ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        # ps.print_stats()
        # print s.getvalue()
        
        return resp

class DummyAccApp(AppProxyThread):
    def chunks(self, l, n):
        for i in xrange(0, len(l), n):
            yield l[i:i + n]

    def handle(self, header, acc_data):
        ACC_SEGMENT_SIZE = 16# (int, float, float, float)
        for chunk in self.chunks(acc_data, ACC_SEGMENT_SIZE):
            (acc_time, acc_x, acc_y, acc_z) = struct.unpack("!ifff", chunk)
            print "time: %d, acc_x: %f, acc_y: %f, acc_x: %f" % \
                    (acc_time, acc_x, acc_y, acc_z)
        return None


if __name__ == "__main__":
    transformer = FaceTransformation()    
    result_queue = list()

    sys.stdout.write("Discovery Control VM\n")
    service_list = get_service_list(sys.argv)
    video_ip = service_list.get(SERVICE_META.VIDEO_TCP_STREAMING_ADDRESS)
    video_port = service_list.get(SERVICE_META.VIDEO_TCP_STREAMING_PORT)

    
    return_addresses = service_list.get(SERVICE_META.RESULT_RETURN_SERVER_LIST)

    # image receiving thread
    video_frame_queue = Queue.Queue(Const.APP_LEVEL_TOKEN_SIZE)
#    video_frame_queue = Queue.Queue(10)
    print "TOKEN SIZE OF OFFLOADING ENGINE: %d" % Const.APP_LEVEL_TOKEN_SIZE
    video_client = AppProxyStreamingClient((video_ip, video_port), video_frame_queue)
    video_client.start()
    video_client.isDaemon = True
    dummy_video_app = DummyVideoApp(video_frame_queue, result_queue, \
            app_id=Protocol_measurement.APP_DUMMY) # dummy app for image processing
    dummy_video_app.start()
    dummy_video_app.isDaemon = True

    # result pub/sub
    result_pub = ResultpublishClient(return_addresses, result_queue)
    result_pub.start()
    result_pub.isDaemon = True

    
    try:
        while True:
            time.sleep(1)
    except Exception as e:
        pass
    except KeyboardInterrupt as e:
        sys.stdout.write("user exits\n")
    finally:
        if transformer is not None:
            transformer.terminate()
        if video_client is not None:
            video_client.terminate()
        if dummy_video_app is not None:
            dummy_video_app.terminate()
        result_pub.terminate()

