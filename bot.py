import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import yt_dlp
import requests
import uuid

# تمكين التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# تعريف حالات المحادثة
SEND_LINK, CHOOSE_FORMAT = range(2)

# إعدادات yt-dlp
ydl_opts_video = {
    'format': 'best[height<=720]',
    'outtmpl': '/tmp/%(title)s.%(ext)s',
    'quiet': True,
}

ydl_opts_audio = {
    'format': 'bestaudio/best',
    'outtmpl': '/tmp/%(title)s.%(ext)s',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'quiet': True,
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """بدء المحادثة وطلب رابط الفيديو."""
    await update.message.reply_text(
        "مرحباً! أرسل لي رابط الفيديو الذي تريد تحميله.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return SEND_LINK

async def receive_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استقبال رابط الفيديو وعرض خيارات التحميل."""
    user = update.message.from_user
    link = update.message.text
    logger.info("رابط من %s: %s", user.first_name, link)
    
    # حفظ الرابط في context
    context.user_data['link'] = link
    
    # إنشاء لوحة المفاتيح مع الخيارات
    keyboard = [['مقطع أصلي', 'صوت فقط']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    await update.message.reply_text(
        "تم استلام الرابط. اختر التنسيق المطلوب:",
        reply_markup=reply_markup,
    )
    return CHOOSE_FORMAT

async def choose_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالجة اختيار التنسيق وتنزيل الملف."""
    user = update.message.from_user
    choice = update.message.text
    link = context.user_data['link']
    
    logger.info("اختيار من %s: %s", user.first_name, choice)
    
    await update.message.reply_text(
        "جاري التحميل، يرجى الانتظار...",
        reply_markup=ReplyKeyboardRemove(),
    )
    
    try:
        if choice == 'مقطع أصلي':
            # تنزيل الفيديو
            with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
                info = ydl.extract_info(link, download=True)
                file_path = ydl.prepare_filename(info)
                
                # إرسال الفيديو
                with open(file_path, 'rb') as video_file:
                    await update.message.reply_video(
                        video=video_file,
                        caption="ها هو الفيديو الذي طلبته!",
                    )
                
                # حذف الملف بعد الإرسال
                os.remove(file_path)
                
        elif choice == 'صوت فقط':
            # تنزيل الصوت
            with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
                info = ydl.extract_info(link, download=True)
                file_path = ydl.prepare_filename(info)
                # تغيير الامتداد إلى mp3 بسبب postprocessor
                audio_path = os.path.splitext(file_path)[0] + '.mp3'
                
                # إرسال الصوت
                with open(audio_path, 'rb') as audio_file:
                    await update.message.reply_audio(
                        audio=audio_file,
                        caption="ها هو الصوت الذي طلبته!",
                    )
                
                # حذف الملف بعد الإرسال
                os.remove(audio_path)
        
        await update.message.reply_text(
            "تم التحميل بنجاح! يمكنك إرسال رابط آخر إذا أردت.",
            reply_markup=ReplyKeyboardRemove(),
        )
        
    except Exception as e:
        logger.error("خطأ أثناء التحميل: %s", e)
        await update.message.reply_text(
            "عذراً، حدث خطأ أثناء معالجة طلبك. يرجى المحاولة مرة أخرى.",
            reply_markup=ReplyKeyboardRemove(),
        )
    
    return SEND_LINK

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """إلغاء المحادثة."""
    user = update.message.from_user
    logger.info("المستخدم %s ألغى المحادثة.", user.first_name)
    await update.message.reply_text(
        "تم الإلغاء. اكتب /start لبدء محادثة جديدة.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END

def main() -> None:
    """تشغيل البوت."""
    # الحصول على التوكن من متغير البيئة
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("لم يتم تعيين توكن البوت في متغيرات البيئة")
        return
    
    # إنشاء التطبيق وتمرير التوكن
    application = Application.builder().token(token).build()

    # إعداد معالج المحادثة
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SEND_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link)],
            CHOOSE_FORMAT: [MessageHandler(filters.Regex('^(مقطع أصلي|صوت فقط)$'), choose_format)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)

    # تشغيل البوت
    application.run_polling()

if __name__ == '__main__':
    main()
