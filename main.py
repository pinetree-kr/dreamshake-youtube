
import argparse

from http import client 
import httplib2
import os
import random
import time

import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow


# 재전송을 명시적으로 설정
httplib2.RETRIES = 1

# 최대 재전송 횟수
MAX_RETRIES = 10

# 해당 익셉션시에 재전송
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError, client.NotConnected,
                        client.IncompleteRead, client.ImproperConnectionState,
                        client.CannotSendRequest, client.CannotSendHeader,
                        client.ResponseNotReady, client.BadStatusLine)

# 해당 HTTP 상태코드(서버 오류)시 재전송
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

# 'client_secret.json' 불러오기
CLIENT_SECRETS_FILE = 'client_secret.json'

# 유튜브 API 설정
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

VALID_PRIVACY_STATUSES = ('public', 'private', 'unlisted')


# 권한요청 및 증명발급
def get_authenticated_service():
    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, SCOPES)
    credentials = flow.run_console()
    return build(API_SERVICE_NAME, API_VERSION, credentials=credentials)


def initialize_upload(youtube, options):
    tags = None
    if options.keywords:
        tags = options.keywords.split(',')

    body = dict(
        snippet=dict(
            title=options.title,
            description=options.description,
            tags=tags,
            categoryId=options.category
        ),
        status=dict(
            privacyStatus=options.privacyStatus
        )
    )

    # 해당 비디오 업로드 요청
    insert_request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=MediaFileUpload(options.file, chunksize=-1, resumable=True)
    )

    resumable_upload(insert_request)

# 파일 전송 실패시 전송재개
def resumable_upload(request):
    response = None
    error = None
    retry = 0
    while response is None:
        try:
            print('Uploading file...')
            status, response = request.next_chunk()
            if response is not None:
                if 'id' in response:
                    print('Video id "%s" was successfully uploaded.' %
                          response['id'])
                else:
                    exit('The upload failed with an unexpected response: %s' % response)
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = 'A retriable HTTP error %d occurred:\n%s' % (e.resp.status,
                                                                     e.content)
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            error = 'A retriable error occurred: %s' % e

        if error is not None:
            print(error)
            retry += 1
            if retry > MAX_RETRIES:
                exit('No longer attempting to retry.')

            max_sleep = 2 ** retry
            sleep_seconds = random.random() * max_sleep
            print('Sleeping %f seconds and then retrying...' % sleep_seconds)
            time.sleep(sleep_seconds)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True, help='Video file to upload')
    parser.add_argument('--title', help='Video title', default='분석영상 테스트')
    parser.add_argument('--description', help='Video description',
                        default='머신러닝 기반의 이미지 프로세싱')
    parser.add_argument('--category', default='22',
                        help='Numeric video category. ' +
                        'See https://developers.google.com/youtube/v3/docs/videoCategories/list')
    parser.add_argument('--keywords', help='Video keywords, comma separated',
                        default='드림쉐이크, 농구, 이미지프로세싱, 머신러닝')
    parser.add_argument('--privacyStatus', choices=VALID_PRIVACY_STATUSES,
                        default='public', help='Video privacy status.')
    args = parser.parse_args()

    youtube = get_authenticated_service()

    try:
        initialize_upload(youtube, args)
    except HttpError as e:
        print('An HTTP error %d occurred:\n%s' % (e.resp.status, e.content))
