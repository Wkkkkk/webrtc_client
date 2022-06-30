import argparse
import asyncio
import logging
import aiohttp

from aiortc import (
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
)
from aiortc.rtcconfiguration import RTCConfiguration, RTCIceServer
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder
from aiortc.contrib.signaling import BYE, add_signaling_arguments, create_signaling


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


    async def connect(self, recoder):
        pc = RTCPeerConnection(configuration=RTCConfiguration(
            iceServers=[RTCIceServer(urls=['stun:stun.l.google.com:19302'])]))

        @pc.on("track")
        def on_track(track):
            print("Receiving %s" % track.kind)
            # if track.kind == "video":
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
        
        await pc.setRemoteDescription(RTCSessionDescription(sdp=self._offer, type='offer'))

        # get SDP answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        # send back answer
        await self.answer(pc.localDescription)
        await recoder.start()


    async def answer(self, answer):
        print("answer:", answer)

        message = {"answer": answer.sdp}
        async with session._http.put(session._session_url, 
                                     headers={'content-type': 'application/whpp+json'}, 
                                     json=message) as response:
            # channel MUST respond with status 204 (no content)
            assert(response.status == 204)
            print("response:", response.status)

            if not response.ok:
                print("error")
        

    async def destroy(self):
        # if self._session_url:
        #     message = {"janus": "destroy", "transaction": transaction_id()}
        #     async with self._http.post(self._session_url, json=message) as response:
        #         data = await response.json()
        #         assert data["janus"] == "success"
        #     self._session_url = None

        if self._http:
            await self._http.close()
            self._http = None


async def run(session, recorder):
    await session.create()

    await session.connect(recorder)

    # exchange media
    print("Exchanging media")
    await asyncio.sleep(600)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser(description="WebRTC client")
    parser.add_argument("--url", required=False, default="https://broadcaster.lab.sto.eyevinn.technology:8443/broadcaster/channel/sthlm")
    args = parser.parse_args()

    # stream url
    url = args.url

    # create signaling and peer connection
    session = WHPPSession(url)

    # create recorder for video
    recorder = MediaRecorder("video.mp4")

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
