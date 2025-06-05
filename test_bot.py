import discord
import google.generativeai as genai
import os
from dotenv import load_dotenv
import asyncio # 用于异步操作，例如 message.channel.typing()

# 1. 加载环境变量
load_dotenv()
GOOGLE_AI_KEY = os.getenv("GOOGLE_AI_KEY")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# --- 检查密钥是否存在 ---
if not GOOGLE_AI_KEY:
    print("错误: .env 文件中未找到 GOOGLE_AI_KEY 或环境变量未设置。")
    exit()
if not DISCORD_BOT_TOKEN:
    print("错误: .env 文件中未找到 DISCORD_BOT_TOKEN 或环境变量未设置。")
    exit()
# --- 密钥检查完毕 ---

# 2. 配置 Google AI
try:
    genai.configure(api_key=GOOGLE_AI_KEY)
    # 使用你选择的预览模型
    # 你可以定义一个系统指令来引导模型的行为
    SYSTEM_INSTRUCTION = "你是一个友好且乐于助人的 Discord 聊天机器人，名叫 'Gemini Bot'。请用简洁明了的方式回答问题。"
    ai_model = genai.GenerativeModel(
        model_name="models/gemini-2.5-flash-preview-05-20", # 更新为你的预览模型
        system_instruction=SYSTEM_INSTRUCTION # 添加系统指令
    )
    print(f"Google AI 模型 ({ai_model.model_name}) 配置成功。")
except Exception as e:
    print(f"配置 Google AI 时出错: {e}")
    exit()

# 3. 配置 Discord Bot
intents = discord.Intents.default()
intents.message_content = True # 必须开启才能读取消息内容
bot_client = discord.Client(intents=intents)

# 4. 存储聊天历史 (每个频道独立)
chat_histories = {} # key: channel_id, value: list of chat messages
MAX_HISTORY_TURNS = 15 # 存储最近15轮对话 (1轮 = 1用户 + 1模型) => 30条消息

# 5. Bot 事件处理
@bot_client.event
async def on_ready():
    print("----------------------------------------")
    print(f'测试机器人已登录: {bot_client.user}')
    print(f'机器人ID: {bot_client.user.id}')
    print("使用方法: @机器人名字 hello")
    print("或: @机器人名字 askai <你的问题>")
    print("或: @机器人名字 clear history (清空当前频道对话历史)")
    print("例如: @机器人名字 askai 中国的首都是哪里？")
    print("在私信 (DM) 中也可以直接发送 'hello', 'askai <你的问题>', 或 'clear history'")
    print("----------------------------------------")

@bot_client.event
async def on_message(message):
    # 忽略机器人自身发送的消息
    if message.author == bot_client.user:
        return

    # 检查机器人是否被提及，或者是否为私信
    if bot_client.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        
        actual_content = ""
        if isinstance(message.channel, discord.DMChannel):
            actual_content = message.content.strip()
        else:
            temp_content = message.content.replace(f"<@{bot_client.user.id}>", "", 1)
            actual_content = temp_content.replace(f"<@!{bot_client.user.id}>", "", 1).strip()
            
            if not actual_content and bot_client.user.mentioned_in(message):
                 await message.reply("你好！你提及了我。试试发送 'hello', 'askai <你的问题>' 或 'clear history'。")
                 return

        print(f"频道ID {message.channel.id} - 收到来自 {message.author.name} 的消息: '{actual_content}' (原始: '{message.content}')")
        
        # 获取或创建当前频道的聊天历史
        channel_id = message.channel.id
        if channel_id not in chat_histories:
            chat_histories[channel_id] = [] # 初始化为空列表
        
        current_channel_history = chat_histories[channel_id]

        # 显示"正在输入..."状态
        async with message.channel.typing():
            if actual_content.lower() == "hello":
                await message.reply("你好！连接正常，我在这里。")
            
            elif actual_content.lower() == "clear history":
                chat_histories[channel_id] = [] # 清空历史
                await message.reply("当前频道的聊天历史已清空。")
                print(f"频道ID {channel_id} - 聊天历史已清空。")

            elif actual_content.lower().startswith("askai "):
                user_prompt = actual_content[len("askai "):].strip()
                
                if not user_prompt:
                    await message.reply("请在 'askai ' 后面提供你的问题。例如: `@机器人名字 askai AI是什么?`")
                    return

                try:
                    print(f"频道ID {channel_id} - 发送给 AI 的用户提问: '{user_prompt}'")

                    # 1. 将用户的新消息添加到历史记录
                    #    Gemini API 需要一个包含 "role" 和 "parts" 的字典列表
                    current_channel_history.append({"role": "user", "parts": [user_prompt]})

                    # 2. 限制历史记录长度 (保留最近N轮对话)
                    #    一轮对话是用户一次提问 + 模型一次回答 (即2条消息)
                    #    所以 MAX_HISTORY_TURNS * 2 是总的消息条数上限
                    if len(current_channel_history) > MAX_HISTORY_TURNS * 2:
                        # 保留最新的 MAX_HISTORY_TURNS * 2 条消息
                        current_channel_history = current_channel_history[-(MAX_HISTORY_TURNS * 2):]
                        chat_histories[channel_id] = current_channel_history # 更新存储的记录
                        print(f"频道ID {channel_id} - 历史记录已裁剪至 {len(current_channel_history)} 条。")


                    # 3. 调用AI模型，传入当前频道的对话历史
                    #    注意：generate_content 的第一个参数是历史列表
                    #    如果历史为空，它只会基于 system_instruction 和当前用户的输入来生成
                    print(f"频道ID {channel_id} - 发送给AI的完整上下文消息数量: {len(current_channel_history)}")
                    if current_channel_history: # 打印最后几条历史用于调试
                        for hist_item_idx, hist_item in enumerate(current_channel_history[-6:]): # 打印最近3轮对话
                            print(f"  Ctx[{len(current_channel_history)-6+hist_item_idx if len(current_channel_history)>6 else hist_item_idx}] Role: {hist_item['role']}, Parts: {str(hist_item['parts'])[:70]}...")


                    # 使用 start_chat 来管理多轮对话状态会更符合 Gemini SDK 的设计
                    # 但为了与你现有的 chat_histories 结构保持一致，我们直接传递历史列表
                    # 如果直接传递历史列表，模型会将其视为一次性的多轮提示。
                    # chat_session = ai_model.start_chat(history=current_channel_history)
                    # response = await asyncio.to_thread(chat_session.send_message, user_prompt) # 如果使用 chat_session

                    # 直接传递历史列表给 generate_content
                    # Gemini API 会自动处理这个列表作为对话历史
                    response = await asyncio.to_thread(ai_model.generate_content, current_channel_history)
                    ai_reply = response.text
                    print(f"频道ID {channel_id} - 从 AI 收到的回复: '{ai_reply[:200]}...'")

                    # 4. 将模型的回复也添加到历史记录 (如果AI成功回复)
                    current_channel_history.append({"role": "model", "parts": [ai_reply]})

                    # 分割长消息 (Discord消息长度限制约为2000字符)
                    if len(ai_reply) > 1950:
                        chunks = [ai_reply[i:i+1950] for i in range(0, len(ai_reply), 1950)]
                        for chunk_num, chunk in enumerate(chunks):
                            await message.reply(f"({chunk_num+1}/{len(chunks)})\n{chunk}")
                    else:
                        await message.reply(ai_reply)

                except Exception as e:
                    error_msg = f"抱歉，尝试回复时遇到错误: {e}"
                    print(f"频道ID {channel_id} - 错误: {error_msg}")
                    await message.reply(error_msg)
                    # 如果AI调用失败，可以选择从历史中移除刚才的用户输入，避免污染历史
                    if current_channel_history and current_channel_history[-1]["role"] == "user":
                        current_channel_history.pop()
                        print(f"频道ID {channel_id} - 因错误已移除最后的用户输入从历史记录。")
            
            elif bot_client.user.mentioned_in(message) and not actual_content : 
                pass # 上面已经有默认回复逻辑
            elif actual_content : # 如果有内容但不是已知命令 (且机器人被提及或在DM中)
                await message.reply("你好！我收到了你的消息。试试发送 'hello', 'askai <你的问题>' 或 'clear history'。")

# 6. 运行 Bot
if __name__ == "__main__":
    print("正在启动机器人...")
    try:
        bot_client.run(DISCORD_BOT_TOKEN)
    except discord.errors.LoginFailure:
        print("错误: Discord Bot Token 无效或不正确。请检查 .env 文件或环境变量。")
    except Exception as e:
        print(f"启动机器人时发生未处理的错误: {e}")