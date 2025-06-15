import asyncio
import logging
import sys
import os
from typing import Dict
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    InlineQuery, 
    InlineQueryResultCachedPhoto,
    InlineQueryResultArticle,
    InputTextMessageContent,
    BufferedInputFile,
    Message
)
from asyncio_throttle import Throttler

from mermaid_renderer import renderer

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

image_cache: Dict[str, str] = {}
throttler = Throttler(rate_limit=2, period=1)

async def upload_image_to_telegram(image_bytes: bytes, diagram_code: str, user_id: int) -> str:
    """Upload image to Telegram and return file_id"""
    try:
        # Create a unique filename
        diagram_hash = hash(diagram_code) % 1000000
        filename = f"mermaid_{diagram_hash}.png"
        
        # Check cache first
        cache_key = str(diagram_hash)
        if cache_key in image_cache:
            logger.info(f"Using cached file_id for diagram {cache_key}")
            return image_cache[cache_key]
        
        # Upload to Telegram by sending to the user who made the query
        photo = BufferedInputFile(image_bytes, filename=filename)
        
        try:
            # Send to user's chat temporarily
            message = await bot.send_photo(
                chat_id=user_id,
                photo=photo,
                caption="🔄 Preparing image for inline mode...",
                disable_notification=True
            )
            file_id = message.photo[-1].file_id  # Get the largest photo
            
            # Delete the temporary message to keep user's chat clean
            await bot.delete_message(chat_id=user_id, message_id=message.message_id)
            
        except Exception as e:
            logger.warning(f"Failed to upload image to user {user_id}: {e}")
            return None
        
        # Cache the file_id
        image_cache[cache_key] = file_id
        logger.info(f"Cached new file_id for diagram {cache_key}")
        
        return file_id
        
    except Exception as e:
        logger.error(f"Error uploading image to Telegram: {e}")
        return None

@dp.inline_query()
async def handle_inline_query(inline_query: InlineQuery):
    """Handle inline queries for Mermaid diagram rendering"""
    query_text = inline_query.query.strip()
    
    async with throttler:
        try:
            if not query_text:
                results = [
                    InlineQueryResultArticle(
                        id="help",
                        title="📝 Enter Mermaid diagram code",
                        description="Type your Mermaid diagram syntax to render it",
                        input_message_content=InputTextMessageContent(
                            message_text="ℹ️ <b>How to use InMermaid Bot:</b>\n\n"
                                        "1. Type <code>@inmermaidbot</code> followed by your Mermaid code\n"
                                        "2. Select the rendered image to send\n"
                                        "3. Or send code directly to @inmermaidbot for higher quality\n\n"
                                        "<b>Example:</b>\n"
                                        "<code>@inmermaidbot graph TD\n    A[Start] --> B[Process]\n    B --> C[End]</code>"
                        )
                    )
                ]
                await inline_query.answer(results, cache_time=300)
                return
            
            # Render the Mermaid diagram
            image_bytes, error_message = await renderer.render_diagram(query_text)
            
            results = []
            
            if image_bytes:
                diagram_id = f"mermaid_{hash(query_text) % 1000000}"
                
                # Upload image and get file_id
                file_id = await upload_image_to_telegram(image_bytes, query_text, inline_query.from_user.id)
                
                if file_id:
                    results.append(
                        InlineQueryResultCachedPhoto(
                            id=diagram_id,
                            photo_file_id=file_id,
                        )
                    )
                else:
                    results.append(
                        InlineQueryResultArticle(
                            id=diagram_id,
                            title="✅ Valid Mermaid Diagram",
                            description=f"Share this diagram code ({len(query_text)} chars)",
                            input_message_content=InputTextMessageContent(
                                message_text=f"🎨 <b>Mermaid Diagram</b>\n\n"
                                            f"<code>{query_text}</code>\n\n"
                                            f"💡 <i>Send this code to @inmermaidbot to get the rendered image!</i>"
                            )
                        )
                    )
            
            if error_message:
                # Error - show error message
                results.append(
                    InlineQueryResultArticle(
                        id="error",
                        title="❌ Syntax Error",
                        description=error_message[:100],
                        input_message_content=InputTextMessageContent(
                            message_text=f"❌ <b>Mermaid Syntax Error:</b>\n\n"
                                        f"{error_message}\n\n"
                                        f"<b>Your code:</b>\n<code>{query_text}</code>\n\n"
                                        f"💡 <i>Check your syntax at https://mermaid.live/</i>"
                        )
                    )
                )
            
            await inline_query.answer(results, cache_time=60)
            
        except Exception as e:
            logger.error(f"Error in inline query handler: {e}")
            error_results = [
                InlineQueryResultArticle(
                    id="system_error",
                    title="❌ System Error",
                    description="Internal error occurred",
                    input_message_content=InputTextMessageContent(
                        message_text=f"❌ <b>System Error:</b>\n\n{str(e)}\n\n"
                                    f"Please try again or contact support."
                    )
                )
            ]
            await inline_query.answer(error_results, cache_time=10)

@dp.message(Command("start"))
async def start_command(message: Message):
    """Handle /start command"""
    welcome_text = (
        "<b>Direct Mode:</b>\n"
        "Send me Mermaid diagram code and I'll render it as an image\n\n"
        "<b>Inline Mode:</b>\n"
        "Use <code>@inmermaidbot your_code</code> in any chat to render and share diagrams\n\n"
        "<b>Example diagram code:</b>\n"
        "<code>graph TD\n"
        "    A[Start] --> B{Decision}\n"
        "    B -->|Yes| C[Action 1]\n"
        "    B -->|No| D[Action 2]\n"
        "    C --> E[End]\n"
        "    D --> E</code>\n\n"
        "Learn more: https://mermaid.js.org/\n"
        "Test syntax: https://mermaid.live/"
    )
    await message.answer(welcome_text)


@dp.message(F.text)
async def handle_mermaid_code(message: Message):
    """Handle text messages containing Mermaid code"""
    mermaid_code = message.text.strip()
    
    if not mermaid_code or mermaid_code.startswith('/'):
        return
    
    await bot.send_chat_action(message.chat.id, "upload_photo")
    
    try:
        logger.info(f"Rendering diagram for user {message.from_user.id}")
        image_bytes, error_message = await renderer.render_diagram(mermaid_code)
        
        if image_bytes:
            photo = BufferedInputFile(image_bytes, filename="mermaid_diagram.png")
            await message.answer_photo(photo)
            logger.info(f"Successfully sent diagram to user {message.from_user.id}")
        else:
            # Send error message
            await message.answer(
                f"❌ <b>Error rendering diagram:</b>\n\n{error_message}\n\n"
                f"<b>Your code:</b>\n<code>{mermaid_code}</code>\n\n"
                f"💡 <i>Check your syntax at https://mermaid.live/</i>"
            )
    
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await message.answer(
            f"❌ <b>System error:</b> {str(e)}\n\n"
            f"Please try again or contact support."
        )

async def main():
    """Main function to start the bot"""
    try:
        # Initialize renderer
        logger.info("Starting Mermaid renderer...")
        await renderer.start()
        
        # Start polling
        logger.info("Starting bot polling...")
        await dp.start_polling(bot)
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
    finally:
        logger.info("Shutting down...")
        await renderer.stop()
        await bot.session.close()

if __name__ == "__main__":
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("BOT_TOKEN not found in environment variables!")
        sys.exit(1)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1) 