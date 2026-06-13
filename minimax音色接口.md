这是minimax的音色接口：
curl 'https://www.minimaxi.com/v1/api/audio/voice/list?device_platform=web&app_id=3001&version_code=22201&biz_id=1&uuid=ccd6f2c4-acf7-45a4-aa89-dabd55f8759e&lang=zh-Hans&device_id=519315478687277064&os_name=Android&browser_name=chrome&device_memory=32&cpu_core_num=20&browser_language=zh-CN&browser_platform=Linux+x86_64&screen_width=2560&screen_height=1440&unix=1780765304000' \
  -H 'accept: application/json, text/plain, */*' \
  -H 'accept-language: zh-CN,zh;q=0.9,en;q=0.8' \
  -H 'content-type: application/json' \
  -b '_gc_usr_id_cs0_d0_sec0_part0=8dde8eb4-a91b-4bce-acfb-c22528e0e2cf; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%2219e983d03bb560-0e1d25932377bf8-1f462c69-3686400-19e983d03bc2eff%22%2C%22first_id%22%3A%22%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTllOTgzZDAzYmI1NjAtMGUxZDI1OTMyMzc3YmY4LTFmNDYyYzY5LTM2ODY0MDAtMTllOTgzZDAzYmMyZWZmIn0%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%22%2C%22value%22%3A%22%22%7D%2C%22%24device_id%22%3A%2219e983d1e904d6-0b686fcfadf7b68-1f462c69-3686400-19e983d1e91d7a%22%7D; _tt_enable_cookie=1; _ttp=01KTC3T8JB7VX6Q932P14JG69H_.tt.1; sensorsdata2015jssdkchannel=%7B%22prop%22%3A%7B%22_sa_channel_landing_url%22%3A%22%22%7D%7D; ttcsid_D0LVH9BC77UCPQOLK3F0=1780765293488::1jG42lA3SegsAQtPNKc8.2.1780765293701.0; ttcsid=1780765293488::vTJhTlqjyZa9sfyGS3Vi.2.1780765293701.0::1.-6153.0::1534.1.908.73::0.0.0; _gc_s_cs0_d0_sec0_part0=rum=0&expire=1780766203966' \
  -H 'origin: https://www.minimaxi.com' \
  -H 'priority: u=1, i' \
  -H 'referer: https://www.minimaxi.com/audio/voices' \
  -H 'sec-ch-ua: "Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "Linux"' \
  -H 'sec-fetch-dest: empty' \
  -H 'sec-fetch-mode: cors' \
  -H 'sec-fetch-site: same-origin' \
  -H 'user-agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36' \
  -H 'yy: eb1bb2fe16c0b196652e05ba5d1e2764' \
  --data-raw '{"is_system":true,"is_collect":false,"page":1,"page_size":30,"filter":[],"user_language":"zh-Hans"}'

  然后请求到数据，提取其中voice_name,voice_id,uniq_id,tag_list,tag_items,description,sample_audio，整理到新的json，输出到sample/中英音色.json