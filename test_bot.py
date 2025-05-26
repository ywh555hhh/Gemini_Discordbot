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
    # 注意：这里使用 gemini-1.5-flash 作为广泛可用的测试模型。
    # 你可以将 "gemini-1.5-flash" 更改为你想要测试的 "gemini-2.5-flash-preview-05-20"。
    # 如果使用预览模型，请确保你的 API 密钥有权限访问它。
    ai_model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    print("Google AI 模型配置成功。")
except Exception as e:
    print(f"配置 Google AI 时出错: {e}")
    exit()

# 3. 配置 Discord Bot
intents = discord.Intents.default()
intents.message_content = True # 必须开启才能读取消息内容
bot_client = discord.Client(intents=intents)

# 4. Bot 事件处理
@bot_client.event
async def on_ready():
    print("----------------------------------------")
    print(f'测试机器人已登录: {bot_client.user}')
    print(f'机器人ID: {bot_client.user.id}')
    print("使用方法: @机器人名字 hello")
    print("或: @机器人名字 askai <你的问题>")
    print("例如: @机器人名字 askai 中国的首都是哪里？")
    print("在私信 (DM) 中也可以直接发送 'hello' 或 'askai <你的问题>'")
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
            # 私信中，直接使用消息内容
            actual_content = message.content.strip()
        else:
            # 在频道中，移除对机器人的提及
            # <@BOT_ID> 或 <@!BOT_ID>
            # bot_client.user.mention 通常是 <@BOT_ID>
            # 确保两种形式的提及都被移除
            temp_content = message.content.replace(f"<@{bot_client.user.id}>", "", 1)
            actual_content = temp_content.replace(f"<@!{bot_client.user.id}>", "", 1).strip()
            
            # 如果移除了提及后内容为空，但消息中确实提及了机器人，
            # 这可能是用户只发送了@机器人而没有其他文本。
            # 这种情况下，我们仍然希望机器人能响应一个默认消息。
            if not actual_content and bot_client.user.mentioned_in(message):
                 await message.reply("你好！你提及了我。试试发送 'hello' 或 'askai <你的问题>'。")
                 return


        print(f"收到来自 {message.author.name} 的消息: '{actual_content}' (原始: '{message.content}')")
        
        # 显示"正在输入..."状态
        async with message.channel.typing():
            if actual_content.lower() == "hello":
                await message.reply("你好！连接正常，我在这里。")
            elif actual_content.lower().startswith("askai "):
                user_prompt = actual_content[len("askai "):].strip()
                
                if not user_prompt:
                    await message.reply("请在 'askai ' 后面提供你的问题。例如: `@机器人名字 askai AI是什么?`")
                    return

                try:
                    print(f"发送给 AI 的内容: '{user_prompt}'")
                    response = await asyncio.to_thread(ai_model.generate_content, user_prompt) # 在线程中运行阻塞IO
                    ai_reply = response.text
                    print(f"从 AI 收到的回复: '{ai_reply[:200]}...'") # 打印部分回复以供调试

                    # 分割长消息 (Discord消息长度限制约为2000字符)
                    if len(ai_reply) > 1950:
                        chunks = [ai_reply[i:i+1950] for i in range(0, len(ai_reply), 1950)]
                        for chunk_num, chunk in enumerate(chunks):
                            await message.reply(f"({chunk_num+1}/{len(chunks)})\n{chunk}")
                    else:
                        await message.reply(ai_reply)
                except Exception as e:
                    error_msg = f"抱歉，尝试回复时遇到错误: {e}"
                    print(error_msg)
                    await message.reply(error_msg)
            elif bot_client.user.mentioned_in(message) and not actual_content: 
                # 如果只是提及了机器人而没有其他内容 (这个条件可能在上面的逻辑中已处理)
                pass # 上面已经有默认回复逻辑
            elif actual_content : # 如果有内容但不是已知命令
                await message.reply("你好！你提及了我。试试发送 'hello' 或 'askai <你的问题>'。")


# 5. 运行 Bot
if __name__ == "__main__":
    print("正在启动机器人...")
    bot_client.run(DISCORD_BOT_TOKEN)