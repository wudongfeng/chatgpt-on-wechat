import time
from typing import List, Tuple

import requests

from bot.bot import Bot
from bot.chatgpt.chat_gpt_session import ChatGPTSession
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from config import conf


class FengliBot(Bot):
    def __init__(self):
        super().__init__()
        self.sessions = SessionManager(ChatGPTSession, model=conf().get("model") or "fengli")

    def reply(self, query, context=None):
        # acquire reply content
        if context.type == ContextType.TEXT:
            logger.info("[FENGLI] query={}".format(query))

            session_id = context["session_id"]
            session = self.sessions.session_query(query, session_id)
            logger.debug("[FENGLI] session query={}".format(session.messages))
            reply_content, err = self._reply_text(session_id, session)
            if err is not None:
                logger.error("[FENGLI] reply error={}".format(err))
                return Reply(ReplyType.ERROR, "我暂时遇到了一些问题，请您稍后重试~")
            logger.debug(
                "[FENGLI] new_query={}, session_id={}, reply_cont={}, completion_tokens={}".format(
                    session.messages,
                    session_id,
                    reply_content["content"],
                    reply_content["completion_tokens"],
                )
            )
            self.sessions.session_reply(reply_content["content"], session_id, reply_content["total_tokens"])
            logger.debug(f"[FENGLI] add reply to session success,reply_content={reply_content['content']}")
            return Reply(ReplyType.TEXT, reply_content["content"])
        else:
            reply = Reply(ReplyType.ERROR, "Bot不支持处理{}类型的消息".format(context.type))
            return reply

    @staticmethod
    def send_post_request(body) -> str:
        url = conf().get('fengli_api', 'http://127.0.0.1:8800/chat')
        headers = {
            "Content-Type": "application/json"
        }
        try:
            response = requests.post(url, json=body, headers=headers)
            response.raise_for_status()  # 检查响应状态码是否为200（成功）
            data = response.json()  # 解析响应的JSON数据

            logger.info(f"Response message: {data['message']}")
            return data.get("message", "[fengli-answer]请求失败")
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error occurred: {http_err}")
        except Exception as err:
            logger.error(f"Other error occurred: {err}")

    def _reply_text(self, session_id: str, session: ChatGPTSession, retry_count=0):
        try:
            query, chat_history = FengliBot._convert_messages_format(session.messages)
            query_body = {
                "bot_id": 1,
                "user_id": "wudongfeng",
                "message": query
            }
            bot_answer = FengliBot.send_post_request(query_body)
            return {
                "total_tokens": 100,
                "completion_tokens": 100,
                "content": bot_answer
            }, None
        except Exception as e:
            if retry_count < 2:
                time.sleep(3)
                logger.warn(f"[FENGLI] Exception: {repr(e)} 第{retry_count + 1}次重试")
                return self._reply_text(session_id, session, retry_count + 1)
            else:
                return None, f"[FENGLI] Exception: {repr(e)} 超过最大重试次数"

    @staticmethod
    def _convert_messages_format(messages) -> Tuple[str, List[dict]]:
        chat_history = []
        for message in messages:
            role = message.get('role')
            if role == 'user':
                content = message.get('content')
                chat_history.append({"role": "user", "content": content, "content_type": "text"})
            elif role == 'assistant':
                content = message.get('content')
                chat_history.append({"role": "assistant", "type": "answer", "content": content, "content_type": "text"})
            elif role == 'system':
                pass
        user_message = chat_history.pop()
        if user_message.get('role') != 'user' or user_message.get('content', '') == '':
            raise Exception('no user message')
        query = user_message.get('content')
        logger.debug("[FENGLI] converted FENGLI messages: {}".format([item for item in chat_history]))
        logger.debug("[FENGLI] user content as query: {}".format(query))
        return query, chat_history
