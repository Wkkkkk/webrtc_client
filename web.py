import argparse
import asyncio
import logging
import aiohttp
import threading
import cv2
from flask import Response, Flask, render_template

from aiortc import (
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
)
from aiortc.rtcconfiguration import RTCConfiguration, RTCIceServer
from aiortc.contrib.media import MediaBlackhole, MediaRecorder
from av import VideoFrame

# initialize the output frame and a lock used to ensure thread-safe
# exchanges of the output frames (useful for multiple browsers/tabs
# are viewing tthe stream)
outputFrame = cv2.imread("default.png")
lock = threading.Lock()

# initialize a flask object
app = Flask(__name__)

@app.route("/")
def index():
    # return the rendered template
    return render_template("index.html")

def generate():
    # grab global references to the output frame and lock variables
    global outputFrame, lock
    # loop over frames from the output stream
    while True:
        # wait until the lock is acquired
        with lock:
            # check if the output frame is available, otherwise skip
            # the iteration of the loop
            if outputFrame is None:
                continue

            # encode the frame in JPEG format
            (flag, encodedImage) = cv2.imencode(".jpg", outputFrame)
            # ensure the frame was successfully encoded
            if not flag:
                print("fail to encode the frame")
                continue

        # yield the output frame in the byte format
        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')


@app.route("/video_feed")
def video_feed():
    # return the response generated along with the specific media
    # type (mime type)
    return Response(generate(), mimetype = "multipart/x-mixed-replace; boundary=frame")


class VideoWrapper(VideoStreamTrack):
    kind = "video"

    def __init__(self, track):
        super().__init__()
        self.track = track


    async def recv(self):
        global outputFrame, lock

        pts, time_base = await self.next_timestamp()

        frame = await self.track.recv()
        frame = frame.to_ndarray(format="bgr24")

        # TODO: self-defined image processing
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (7, 7), 0)

        # acquire the lock, set the output frame, and release the lock
        with lock:
            outputFrame = gray.copy()

        frame = VideoFrame.from_ndarray(frame, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base

        return frame


class WHPPSession:
    def __init__(self, url):
        self._http = None
        self._root_url = url
        self._session_url = None
        self._offer = None


    async def create(self):
        self._http = aiohttp.ClientSession()
        message = {}
        async with self._http.post(self._root_url,
                                   headers={
                                       'Content-Type': 'application/json'},
                                   json=message) as response:
            # channel MUST respond with status 201 (created)
            assert(response.status == 201)

            # the initial SDP offer and additional metadata about the media streams
            data = await response.json()
            # print("data:", data)
            self._offer = data['offer']

            # viewer resource URL
            location = response.headers.get('location')
            print("location:", location)

            self._session_url = location


    async def connect(self, recorder):
        pc = RTCPeerConnection(configuration=RTCConfiguration(
            iceServers=[RTCIceServer(urls=['stun:stun.l.google.com:19302'])]))

        @pc.on("track")
        def on_track(track):
            print("Receiving %s" % track.kind)
            if track.kind == "video":
                t = VideoWrapper(track)
                pc.addTrack(t)

            recorder.addTrack(track)
            
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            print("Connection state is %s" % pc.connectionState)
            if pc.connectionState == "failed":
                await pc.close()

        @pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            print("Ice connection state is %s" % pc.iceConnectionState)
            if pc.iceConnectionState == "failed":
                await pc.close()
        
        @pc.on("icegatheringstatechange")
        async def on_icegetheringstatechange():
            print("Ice gathering state is %s" % pc.iceGatheringState)
            if pc.iceGatheringState == "complete" and pc.localDescription is not None:
                await self.sendCandidates(pc.localDescription)
        
        await pc.setRemoteDescription(RTCSessionDescription(sdp=self._offer, type='offer'))

        # get SDP answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        # send back answer
        await self.answer(pc.localDescription)
        await recorder.start()


    async def answer(self, answer):
        # print("answer:", answer)
        message = {"answer": answer.sdp}
        async with session._http.put(session._session_url, 
                                     headers={'content-type': 'application/whpp+json'}, 
                                     json=message) as response:
            # channel MUST respond with status 204 (no content)
            # assert(response.status == 204)

            if not response.ok:
                print("error:", response.status)
        

    async def sendCandidates(self, candidates):
        message = {"candidate": candidates.sdp}
        async with session._http.patch(session._session_url, 
                                     headers={'content-type': 'application/whpp+json'}, 
                                     json=message) as response:
            # channel MUST respond with status 204 (no content) or 405 (method not allowed)
            # assert(response.status == 204 or response.status == 405)

            if not response.ok:
                print("error:", response.status)


    async def destroy(self):
        if self._http:
            await self._http.close()
            self._http = None


async def run(session, recorder):
    await session.create()

    await session.connect(recorder)

    # exchange media
    await asyncio.sleep(600)

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser(description="WebRTC client")
    parser.add_argument("--port", required=False, default="8000")
    parser.add_argument("--url", required=False, 
        default="https://broadcaster.lab.sto.eyevinn.technology:8443/broadcaster/channel/sthlm")
    args = parser.parse_args()

    # stream url
    url = args.url
    port = args.port

    # create signaling and peer connection
    session = WHPPSession(url)

    # create recorder for video
    # recorder = MediaRecorder("video.mp4")
    recorder = MediaBlackhole()

    # start the flask app
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)).start()

    # start the rtc loop
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            run(session=session, recorder=recorder)
        )
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(session.destroy())
    
    loop.run_until_complete(recorder.stop())
