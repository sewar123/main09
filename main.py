import logging
import random
import string
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    CallbackQueryHandler, 
    ContextTypes, 
    MessageHandler, 
    filters,
    ConversationHandler
)

# إعدادات البوت - تم التعديل
TOKEN = "8537166984:AAHA_j27AuYsDy_OX2AX5PEh4_YiwPU-GlQ"  #توكن 
ADMIN_ID = 5504502257   # ايدي 
REPORTS_CHANNEL = "@dibogigig"  # قناة التقارير

# حالات المحادثة
CHECK_SUB_BEFORE_MATH = 1
VERIFY_SYRIAN_PHONE = 2
VERIFY_CODE = 3
VERIFY_MATH = 4
WITHDRAW_AMOUNT = 5
WITHDRAW_DETAILS = 6
CHANGE_MIN_WITHDRAW = 7
ENTER_GIFT_CODE = 8
CREATE_GIFT_CODE = 9
CHANGE_REFERRAL_BONUS = 10
CHANGE_DAILY_BONUS = 11
TRANSFER_AMOUNT = 12
TRANSFER_USER = 13
BROADCAST_MESSAGE = 14
MANUAL_BAN_USER = 15
UNBAN_USER = 16
CHANGE_TRANSFER_FEE = 17
CHANGE_REPORTS_CHANNEL = 18

# قنوات الاشتراك الإلزامية
REQUIRED_CHANNELS = [
    {"username": "@One_Dot_1bot", "id": 
-1003104901672},
]

# طرق السحب المتاحة
WITHDRAWAL_METHODS = {
    "syriatel_cash": {
        "name": "سريتيل كاش",
        "input_prompt": "📱 أدخل رقم الهاتف الذي ستستلم عليه المبلغ (سريتيل كاش):",
        "input_type": "syrian_phone",
        "placeholder": "مثال: 0991234567",
        "validate_phone": True
    },
    "sham_cash_syr": {
        "name": "شام كاش سوري",
        "input_prompt": "📍 أدخل عنوان الاستلام لشام كاش (ليرة سورية):",
        "input_type": "address",
        "placeholder": "",
        "validate_phone": False
    },
    "sham_cash_usd": {
        "name": "شام كاش دولار",
        "input_prompt": "📍 أدخل عنوان الاستلام لشام كاش (دولار):",
        "input_type": "address",
        "placeholder": "",
        "validate_phone": False
    },
    "paynes": {
        "name": "Paynes",
        "input_prompt": "🏦 أدخل رقم الحساب أو العنوان لـ Paynes:",
        "input_type": "account",
        "placeholder": "مثال: رقم الحساب أو العنوان",
        "validate_phone": False
    }
}

# تخزين البيانات
users_data = {}
withdrawals_data = {}
bot_settings = {
    'min_withdraw': 10000,
    'referral_bonus': 30,
    'daily_bonus_min': 5,
    'daily_bonus_max': 10,
    'gift_code_min': 500,
    'gift_code_max': 5000,
    'gift_code_expiry_days': 3,
    'transfer_fee_percent': 5,
    'min_transfer': 100,
}
gift_codes = {}
used_gift_codes = {}
user_referrals = {}
withdrawal_counter = 0
banned_users = {}
transfer_logs = []

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توليد كود هدية عشوائي
def generate_gift_code(length=10):
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# دالة تحويل الأرقام العربية إلى الإنجليزية
def convert_arabic_to_english(phone):
    arabic_to_english = {
        '٠': '0', '۰': '0',
        '١': '1', '۱': '1',
        '٢': '2', '۲': '2',
        '٣': '3', '۳': '3',
        '٤': '4', '۴': '4',
        '٥': '5', '۵': '5',
        '٦': '6', '۶': '6',
        '٧': '7', '۷': '7',
        '٨': '8', '۸': '8',
        '٩': '9', '۹': '9'
    }
    for arabic, english in arabic_to_english.items():
        phone = phone.replace(arabic, english)
    return phone

# التحقق من رقم الهاتف السوري - محسن
def verify_syrian_phone(phone_number):
    phone = str(phone_number).strip()
    phone = convert_arabic_to_english(phone)
    phone = re.sub(r'\s+', '', phone)
    phone = re.sub(r'[-().+]', '', phone)
    
    if not re.match(r'^\d+$', phone):
        return False, phone
    
    if phone.startswith('00'):
        phone = phone[2:]
    elif phone.startswith('+'):
        phone = phone[1:]
    
    if phone.startswith('963'):
        phone = '0' + phone[3:]
    elif phone.startswith('9'):
        phone = '0' + phone
    
    pattern = r'^09\d{8}$'
    if re.match(pattern, phone):
        return True, phone
    
    return False, phone

# الحصول على إعدادات البوت
def get_setting(key, default=None):
    return bot_settings.get(key, default)

# تحديث إعدادات البوت
def update_setting(key, value):
    bot_settings[key] = value
    logger.info(f"✅ تم تحديث الإعداد {key} إلى {value}")

# الحصول على الحد الأدنى للسحب
def get_min_withdraw():
    return bot_settings['min_withdraw']

# التحقق إذا كان المستخدم سوريًا
def is_user_syrian(user_id):
    if user_id in users_data:
        return users_data[user_id].get('phone_verified', False)
    return False

# إضافة مستخدم جديد (دون مكافآت)
async def add_user_without_bonus(user_id, username, first_name, last_name, invited_by=None):
    if user_id not in users_data:
        users_data[user_id] = {
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'balance': 0,
            'invited_by': invited_by,
            'join_date': datetime.now(),
            'last_bonus_date': None,
            'total_gift_earned': 0,
            'referred_count': 0
        }
        logger.info(f"✅ تمت إضافة مستخدم جديد: {user_id}")
    else:
        logger.info(f"✅ المستخدم موجود مسبقاً: {user_id}")

# إكمال عملية التسجيل مع المكافآت
async def complete_user_registration(user_id, username, first_name, last_name, invited_by, context):
    welcome_bonus = random.choice([20, 30, 10])
    
    # تحديث بيانات المستخدم
    if user_id not in users_data:
        users_data[user_id] = {
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'balance': welcome_bonus,
            'invited_by': invited_by,
            'join_date': datetime.now(),
            'last_bonus_date': None,
            'total_gift_earned': 0,
            'referred_count': 0
        }
    else:
        users_data[user_id]['balance'] = welcome_bonus
    
    # إذا كان هناك مدعو، سجل الإحالة ومنح المكافأة
    if invited_by and invited_by != user_id and invited_by in users_data:
        # تسجيل الإحالة
        if invited_by not in user_referrals:
            user_referrals[invited_by] = []
        user_referrals[invited_by].append(user_id)
        
        # منح مكافأة الإحالة للمدعو
        referral_bonus = bot_settings['referral_bonus']
        users_data[invited_by]['balance'] += referral_bonus
        users_data[invited_by]['referred_count'] = len(user_referrals[invited_by])
        
        # إرسال إشعار للمدعو
        try:
            await context.bot.send_message(
                invited_by,
                f"🎉 تمت إحالة جديدة!\n\n"
                f"• المستخدم: @{username if username else first_name}\n"
                f"• تم حل السؤال الرياضي بنجاح\n"
                f"• تم إضافة {referral_bonus} ليرة لرصيدك\n"
                f"• الرصيد الحالي: {users_data[invited_by]['balance']} ليرة\n"
                f"• إجمالي إحالاتك: {len(user_referrals[invited_by])}"
            )
            logger.info(f"✅ تم إرسال إشعار إحالة للمستخدم {invited_by}")
        except Exception as e:
            logger.error(f"❌ خطأ في إرسال إشعار الإحالة: {e}")
    
    logger.info(f"✅ تم إكمال تسجيل المستخدم {user_id} مع مكافأة {welcome_bonus} ليرة")
    return welcome_bonus

# منع مستخدم
def ban_user(user_id, reason="استخدام رقم غير سوري"):
    banned_users[user_id] = {
        'reason': reason,
        'banned_at': datetime.now(),
        'banned_by': 'system'
    }
    logger.info(f"⛔ تم منع المستخدم {user_id}: {reason}")
    
    # إرسال تقرير الحظر
    try:
        user_data = users_data.get(user_id, {})
        send_report_to_channel(
            "⛔ مستخدم محظور!",
            f"""
🚫 تم حظر مستخدم
👤 المستخدم: {user_data.get('first_name', 'مجهول')} (@{user_data.get('username', 'لا يوجد')})
🆔 المعرف: {user_id}
📞 الرقم: {user_data.get('syrian_phone', 'غير معروف')}
🚫 السبب: {reason}
👮‍♂️ تم الحظر بواسطة: النظام
📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
        )
    except Exception as e:
        logger.error(f"خطأ في إرسال تقرير الحظر: {e}")

# منع مستخدم يدويًا
def manual_ban_user(user_id, reason, admin_id):
    banned_users[user_id] = {
        'reason': reason,
        'banned_at': datetime.now(),
        'banned_by': admin_id
    }
    logger.info(f"⛔ تم منع المستخدم {user_id} يدوياً من قبل {admin_id}: {reason}")
    
    # إرسال تقرير الحظر اليدوي
    try:
        user_data = users_data.get(user_id, {})
        send_report_to_channel(
            "⛔ حظر يدوي!",
            f"""
🚫 تم حظر مستخدم يدوياً
👤 المستخدم: {user_data.get('first_name', 'مجهول')} (@{user_data.get('username', 'لا يوجد')})
🆔 المعرف: {user_id}
📞 الرقم: {user_data.get('syrian_phone', 'غير معروف')}
🚫 السبب: {reason}
👮‍♂️ تم الحظر بواسطة: المطور ({admin_id})
📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
        )
    except Exception as e:
        logger.error(f"خطأ في إرسال تقرير الحظر اليدوي: {e}")

# فك حظر مستخدم
def unban_user(user_id):
    if user_id in banned_users:
        banned_users.pop(user_id)
        logger.info(f"✅ تم فك حظر المستخدم {user_id}")
        
        # إرسال تقرير فك الحظر
        try:
            user_data = users_data.get(user_id, {})
            send_report_to_channel(
                "✅ فك حظر!",
                f"""
🔓 تم فك حظر مستخدم
👤 المستخدم: {user_data.get('first_name', 'مجهول')} (@{user_data.get('username', 'لا يوجد')})
🆔 المعرف: {user_id}
📞 الرقم: {user_data.get('syrian_phone', 'غير معروف')}
📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال تقرير فك الحظر: {e}")
        
        return True
    return False

# التحقق إذا كان المستخدم ممنوعًا
def is_user_banned(user_id):
    return user_id in banned_users

# التحقق من صلاحية المستخدم لاستخدام البوت
async def check_user_access(user_id, context=None):
    if is_user_banned(user_id):
        ban_info = banned_users[user_id]
        reason = ban_info.get('reason', 'غير محدد')
        banned_by = ban_info.get('banned_by', 'النظام')
        banned_at = ban_info.get('banned_at', datetime.now())
        
        keyboard = []
        if context and context.bot and user_id == ADMIN_ID:
            keyboard = [
                [InlineKeyboardButton("🔓 فك حظر رقم", callback_data=f"unban_{user_id}")],
                [InlineKeyboardButton("🔄 إعادة التحقق", callback_data="reverify_phone")]
            ]
        
        message = f"""⛔ حسابك ممنوع من استخدام البوت

🚫 السبب: {reason}
👤 تم الحظر بواسطة: {banned_by}
📅 تاريخ الحظر: {banned_at.strftime('%Y-%m-%d %H:%M')}
📞 البوت مخصص فقط للمواطنين السوريين

📢 للاستفسار: @Sports_5K"""
        
        return False, "ممنوع", message, keyboard
    
    if not is_user_syrian(user_id):
        if context and user_id not in users_data:
            return True, "new_user", None, None
        return False, "not_syrian", "📵 يجب التحقق من هويتك السورية أولاً.\nاستخدم /start للبدء.", None
    
    return True, "verified", None, None

# الحصول على رصيد المستخدم
def get_balance(user_id):
    if user_id in users_data:
        return users_data[user_id]['balance']
    return 0

# تحديث الرصيد
def update_balance(user_id, amount):
    if user_id in users_data:
        users_data[user_id]['balance'] += amount
        if amount > 0:
            users_data[user_id]['total_gift_earned'] += amount
        return True
    return False

# تحويل الرصيد بين المستخدمين
def transfer_balance(from_user_id, to_user_id, amount):
    if from_user_id not in users_data or to_user_id not in users_data:
        return False, "أحد المستخدمين غير موجود"
    
    if users_data[from_user_id]['balance'] < amount:
        return False, "رصيدك غير كافي"
    
    fee_percent = bot_settings['transfer_fee_percent']
    fee = int((amount * fee_percent) / 100)
    net_amount = amount - fee
    
    users_data[from_user_id]['balance'] -= amount
    users_data[to_user_id]['balance'] += net_amount
    
    transfer_logs.append({
        'from_user_id': from_user_id,
        'to_user_id': to_user_id,
        'amount': amount,
        'fee': fee,
        'net_amount': net_amount,
        'timestamp': datetime.now()
    })
    
    # إرسال تقرير التحويل
    try:
        from_user = users_data[from_user_id]
        to_user = users_data[to_user_id]
        send_report_to_channel(
            "🔄 تحويل رصيد!",
            f"""
💸 عملية تحويل رصيد
👤 المرسل: {from_user['first_name']} (@{from_user.get('username', 'لا يوجد')})
🆔 المعرف: {from_user_id}
👤 المستلم: {to_user['first_name']} (@{to_user.get('username', 'لا يوجد')})
🆔 المعرف: {to_user_id}
💰 المبلغ: {amount} ليرة
💸 الرسوم: {fee} ليرة ({fee_percent}%)
✅ المبلغ الصافي: {net_amount} ليرة
📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
        )
    except Exception as e:
        logger.error(f"خطأ في إرسال تقرير التحويل: {e}")
    
    return True, f"تم التحويل بنجاح! الرسوم: {fee} ليرة ({fee_percent}%)"

# إرسال تقرير إلى قناة التقارير
def send_report_to_channel(title, content):
    """إرسال تقرير إلى قناة التقارير"""
    try:
        report = f"""
{title}
{'-'*30}
{content}
{'-'*30}
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        # في تطبيق حقيقي، سيتم إرسال هذا إلى القناة
        # await context.bot.send_message(chat_id=REPORTS_CHANNEL, text=report)
        logger.info(f"📊 تقرير: {title}")
        logger.info(f"📋 المحتوى: {content}")
    except Exception as e:
        logger.error(f"خطأ في إرسال التقرير: {e}")

# إرسال تقرير مستخدم جديد
async def send_new_user_report(context, user_id, username, first_name, phone):
    """إرسال تقرير مستخدم جديد إلى قناة التقارير"""
    try:
        report = f"""
🟢 مستخدم جديد انضم للبوت!
🆔 المعرف: {user_id}
👤 الاسم: {first_name}
📱 اليوزر: @{username}
📞 الرقم: {phone}
📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        await context.bot.send_message(chat_id=REPORTS_CHANNEL, text=report)
    except Exception as e:
        logger.error(f"خطأ في إرسال تقرير المستخدم الجديد: {e}")

# إرسال تقرير سحب
async def send_withdrawal_report(context, withdrawal_data, user_data):
    """إرسال تقرير سحب إلى قناة التقارير"""
    try:
        report = f"""
💰 عملية سحب جديدة!
👤 المستخدم: {user_data['first_name']} (@{user_data.get('username', 'لا يوجد')})
🆔 المعرف: {withdrawal_data['user_id']}
💰 المبلغ: {withdrawal_data['amount']} ليرة
💳 الطريقة: {WITHDRAWAL_METHODS.get(withdrawal_data['method'], {}).get('name', 'غير معروف')}
📋 التفاصيل: {withdrawal_data['receiver_info']}
🆔 رقم الطلب: #{withdrawal_data.get('id', 'N/A')}
📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        await context.bot.send_message(chat_id=REPORTS_CHANNEL, text=report)
    except Exception as e:
        logger.error(f"خطأ في إرسال تقرير السحب: {e}")

# إرسال تقرير معالجة السحب
async def send_withdrawal_processed_report(context, withdrawal_id, processor_id):
    """إرسال تقرير معالجة سحب إلى قناة التقارير"""
    try:
        withdrawal = withdrawals_data.get(withdrawal_id, {})
        user_id = withdrawal.get('user_id')
        user_data = users_data.get(user_id, {})
        
        report = f"""
✅ عملية سحب مكتملة!
👤 المستخدم: {user_data.get('first_name', 'مجهول')} (@{user_data.get('username', 'لا يوجد')})
🆔 المعرف: {user_id}
💰 المبلغ: {withdrawal.get('amount', 0)} ليرة
💳 الطريقة: {WITHDRAWAL_METHODS.get(withdrawal.get('method'), {}).get('name', 'غير معروف')}
👨‍💼 تمت المعالجة بواسطة: {processor_id}
🆔 رقم الطلب: #{withdrawal_id}
📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        await context.bot.send_message(chat_id=REPORTS_CHANNEL, text=report)
    except Exception as e:
        logger.error(f"خطأ في إرسال تقرير معالجة السحب: {e}")

# إرسال تقرير كود الهدية
async def send_gift_code_report(context, user_id, gift_code, amount):
    """إرسال تقرير استخدام كود هدية إلى قناة التقارير"""
    try:
        user_data = users_data.get(user_id, {})
        report = f"""
🎁 كود هدية مستخدم!
👤 المستخدم: {user_data.get('first_name', 'مجهول')} (@{user_data.get('username', 'لا يوجد')})
🆔 المعرف: {user_id}
🎁 كود الهدية: {gift_code}
💰 المبلغ: {amount} ليرة
📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        await context.bot.send_message(chat_id=REPORTS_CHANNEL, text=report)
    except Exception as e:
        logger.error(f"خطأ في إرسال تقرير كود الهدية: {e}")

# إرسال تقرير الإحالة
async def send_referral_report(context, inviter_id, new_user_id, new_user_name, bonus_amount):
    """إرسال تقرير إحالة جديدة إلى قناة التقارير"""
    try:
        inviter_data = users_data.get(inviter_id, {})
        report = f"""
🤝 إحالة جديدة!
👤 المدعو: {inviter_data.get('first_name', 'مجهول')} (@{inviter_data.get('username', 'لا يوجد')})
🆔 المعرف: {inviter_id}
👤 المستخدم الجديد: {new_user_name}
🆔 المعرف الجديد: {new_user_id}
💰 مكافأة الإحالة: {bonus_amount} ليرة
📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        await context.bot.send_message(chat_id=REPORTS_CHANNEL, text=report)
    except Exception as e:
        logger.error(f"خطأ في إرسال تقرير الإحالة: {e}")

# التحقق من اشتراك المستخدم في القناة
async def check_subscription(context, user_id):
    channel = REQUIRED_CHANNELS[0]
    try:
        chat_member = await context.bot.get_chat_member(chat_id=channel["id"], user_id=user_id)
        if chat_member.status in ['left', 'kicked']:
            return False, channel["username"]
    except Exception as e:
        logger.error(f"خطأ في التحقق من القناة: {e}")
        return False, channel["username"]
    return True, None

# التحقق من الاشتراك والتحقق السوري
async def check_subscription_and_verification(user_id, context, callback_query=None, message=None):
    """التحقق من الاشتراك والتحقق السوري قبل تنفيذ أي أمر"""
    
    # التحقق من الحظر
    if is_user_banned(user_id):
        if callback_query:
            await callback_query.edit_message_text("⛔ حسابك ممنوع من استخدام البوت.")
        elif message:
            await message.reply_text("⛔ حسابك ممنوع من استخدام البوت.")
        return False, "banned"
    
    # التحقق من التحقق السوري
    if not is_user_syrian(user_id):
        if callback_query:
            await callback_query.edit_message_text("📵 يجب التحقق من هويتك السورية أولاً.\nاستخدم /start للبدء.")
        elif message:
            await message.reply_text("📵 يجب التحقق من هويتك السورية أولاً.\nاستخدم /start للبدء.")
        return False, "not_syrian"
    
    # التحقق من الاشتراك
    is_subscribed, channel = await check_subscription(context, user_id)
    if not is_subscribed:
        if callback_query:
            keyboard = [
                [InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{channel[1:]}")],
                [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await callback_query.edit_message_text(
                f"⚠️ يجب عليك الاشتراك في القناة {channel} أولاً!",
                reply_markup=reply_markup
            )
        elif message:
            keyboard = [
                [InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{channel[1:]}")],
                [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await message.reply_text(
                f"⚠️ يجب عليك الاشتراك في القناة {channel} أولاً!",
                reply_markup=reply_markup
            )
        return False, "not_subscribed"
    
    return True, "verified"

# معالجة جهة الاتصال المرسلة مع نظام الكود
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    contact = update.message.contact
    
    if contact.user_id != user.id:
        await update.message.reply_text(
            "❌ يجب مشاركة رقم هاتفك الشخصي فقط!",
            reply_markup=ReplyKeyboardRemove()
        )
        return VERIFY_SYRIAN_PHONE
    
    phone_number = contact.phone_number
    is_valid, clean_phone = verify_syrian_phone(phone_number)
    
    if not is_valid:
        if user.id == ADMIN_ID:
            await update.message.reply_text(
                f"❌ الرقم الذي شاركته ليس سوريًا!\n\n"
                f"📱 الرقم: {phone_number}\n"
                f"🔢 تم تحويله إلى: {clean_phone}\n\n"
                f"📞 يرجى مشاركة رقم سوري صحيح (يبدأ بـ 09 ويتكون من 10 أرقام)."
            )
            return VERIFY_SYRIAN_PHONE
        else:
            ban_reason = f"محاولة استخدام رقم غير سوري من جهة اتصال: {phone_number}"
            ban_user(user.id, ban_reason)
            
            ban_message = f"""
⛔ تم حظر حسابك!

🚫 الرقم الذي شاركته: {phone_number}
📌 هذا الرقم ليس سوريًا.

📢 البوت مخصص حصرياً للمواطنين السوريين.
📞 يجب استخدام رقم هاتف سوري (يبدأ بـ 09 ويتكون من 10 أرقام).

❌ لن تتمكن من استخدام البوت بعد الآن.
            """
            
            await update.message.reply_text(ban_message)
            
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"🚨 محاولة استخدام غير سوري من جهة اتصال!\n\n"
                    f"👤 المستخدم: {user.first_name} (@{user.username})\n"
                    f"🆔 المعرف: {user.id}\n"
                    f"📱 الرقم المدخل: {phone_number}\n"
                    f"📞 الرقم المحول: {clean_phone}\n"
                    f"⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"✅ تم حظر المستخدم تلقائياً."
                )
            except Exception as e:
                logger.error(f"خطأ في إرسال إشعار الحظر: {e}")
            
            return ConversationHandler.END
    
    verification_code = random.randint(100000, 999999)
    context.user_data['verification_code'] = verification_code
    context.user_data['syrian_phone'] = clean_phone
    context.user_data['verification_time'] = datetime.now()
    
    await update.message.reply_text(
        f"✅ تم التحقق من الرقم السوري: {clean_phone}\n\n"
       
    "📣 *معلومات مهمة عن نظام الحماية*\n\n"
    
    "1. 🔐 *نظام التحقق* هذا مخصص فقط للمواطنين السوريين لضمان أن البوت يستخدم من قبل أشخاص حقيقيين.\n\n"
    
    "2. 🛡️ *نظام الحماية القوي* يمنع الاحتيال والتسلل إلى حسابات المستخدمين.\n\n"
    
    "3. 📲 *خصوصية البيانات*: لا يتم مشاركة بياناتك مع أي طرف خارجي، وهي محفوظة بشكل آمن.\n\n"
    
    "4. 🎯 *الهدف*: حماية المستخدمين السوريين وتقديم خدمة آمنة.\n\n"
    
    "👇 *الرجاء إرسال الكود الموجود  للتحقق من أنك إنسان*"

        f"🔢  الكود: {verification_code} \n\n"
        f"",
        reply_markup=ReplyKeyboardRemove()
    )
    
    return VERIFY_CODE

# معالجة الرسائل النصية أثناء التحقق - لحظر من يكتب الرقم يدوياً
async def handle_text_during_verification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # إذا كان المستخدم هو المطور، نسمح له بإدخال الرقم يدوياً
    if user_id == ADMIN_ID:
        return await verify_syrian_phone_handler(update, context)
    
    # حظر أي مستخدم عادي يحاول كتابة الرقم
    ban_reason = f"محاولة كتابة الرقم يدوياً: {update.message.text}"
    ban_user(user_id, ban_reason)
    
    ban_message = f"""
⛔ تم حظر حسابك!

🚫 لقد قمت بمحاولة كتابة الرقم يدوياً: {update.message.text}
📌 النظام يطلب مشاركة الرقم عبر زر 'مشاركة جهة الاتصال' فقط.

📢 البوت مخصص حصرياً للمواطنين السوريين.
📞 يجب استخدام رقم هاتف سوري (يبدأ بـ 09 ويتكون من 10 أرقام) ومشاركته عبر زر 'مشاركة جهة الاتصال'.

❌ لن تتمكن من استخدام البوت بعد الآن.
    """
    
    await update.message.reply_text(ban_message)
    
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"🚨 محاولة كتابة رقم يدوياً!\n\n"
            f"👤 المستخدم: {user.first_name} (@{user.username})\n"
            f"🆔 المعرف: {user_id}\n"
            f"📱 النص المدخل: {update.message.text}\n"
            f"⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"✅ تم حظر المستخدم تلقائياً."
        )
    except Exception as e:
        logger.error(f"خطأ في إرسال إشعار الحظر: {e}")
    
    return ConversationHandler.END

# معالجة الرسائل النصية للرقم - للمطور فقط
async def verify_syrian_phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # هذه الوظيفة للمطور فقط
    if user_id != ADMIN_ID:
        ban_reason = f"محاولة كتابة الرقم يدوياً: {update.message.text}"
        ban_user(user_id, ban_reason)
        
        ban_message = f"""
⛔ تم حظر حسابك!

🚫 لقد قمت بمحاولة كتابة الرقم يدوياً: {update.message.text}
📌 النظام يطلب مشاركة الرقم عبر زر 'مشاركة جهة الاتصال' فقط.

📢 البوت مخصص حصرياً للمواطنين السوريين.
📞 يجب استخدام رقم هاتف سوري (يبدأ بـ 09 ويتكون من 10 أرقام) ومشاركته عبر زر 'مشاركة جهة الاتصال'.

❌ لن تتمكن من استخدام البوت بعد الآن.
        """
        
        await update.message.reply_text(ban_message)
        
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"🚨 محاولة كتابة رقم يدوياً!\n\n"
                f"👤 المستخدم: {user.first_name} (@{user.username})\n"
                f"🆔 المعرف: {user_id}\n"
                f"📱 النص المدخل: {update.message.text}\n"
                f"⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"✅ تم حظر المستخدم تلقائياً."
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال إشعار الحظر: {e}")
        
        return ConversationHandler.END
    
    phone_number = update.message.text.strip()
    is_valid, clean_phone = verify_syrian_phone(phone_number)
    
    if not is_valid:
        await update.message.reply_text(
            f"❌ الرقم الذي أدخلته ليس سوريًا!\n\n"
            f"📱 الرقم المدخل: {phone_number}\n"
            f"🔢 تم تحويله إلى: {clean_phone}\n\n"
            f"📞 يرجى إدخال رقم سوري صحيح (يبدأ بـ 09 ويتكون من 10 أرقام)."
        )
        return VERIFY_SYRIAN_PHONE
    
    verification_code = random.randint(100000, 999999)
    context.user_data['verification_code'] = verification_code
    context.user_data['syrian_phone'] = clean_phone
    context.user_data['verification_time'] = datetime.now()
    
    await update.message.reply_text(
        f"✅ تم التحقق من الرقم السوري: {clean_phone}\n\n"
        f"🔐 خطوة التحقق النهائية\n\n"
        f"📱 تم إرسال كود التحقق إلى رقمك:\n"
        f"🔢 **الكود: {verification_code}**\n\n"
        f"الرجاء إرسال هذا الكود لتفعيل حسابك:\n"
        f"❌ للإلغاء، اضغط /cancel",
        reply_markup=ReplyKeyboardRemove()
    )
    
    return VERIFY_CODE

# أمر /start مع التحقق الشامل
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # ✅ إصلاح المشكلة: تخزين رابط الإحالة بشكل آمن
    invited_by = None
    if context.args and len(context.args) > 0:
        try:
            invited_by = int(context.args[0])
            logger.info(f"📝 المستخدم {user_id} دخل عبر رابط دعوة من {invited_by}")
            
            # ✅ حفظ رابط الإحالة في context.user_data أولاً
            context.user_data['invited_by'] = invited_by
            context.user_data['referral_entry'] = True  # علامة أن المستخدم دخل من رابط إحالة
        except:
            invited_by = None
    
    # ✅ إصلاح: حفظ معلومات المستخدم في context.user_data
    context.user_data['user_id'] = user_id
    context.user_data['username'] = user.username
    context.user_data['first_name'] = user.first_name
    context.user_data['last_name'] = user.last_name
    
    has_access, access_type, message, keyboard = await check_user_access(user_id, context)
    
    if not has_access:
        if access_type == "ممنوع":
            if keyboard:
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(message, reply_markup=reply_markup)
            else:
                await update.message.reply_text(message)
            return ConversationHandler.END
        else:
            await update.message.reply_text(message)
            return ConversationHandler.END
    
    if user_id in users_data and is_user_syrian(user_id):
        is_subscribed, channel = await check_subscription(context, user_id)
        
        if not is_subscribed:
            keyboard = [
                [InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{channel[1:]}")],
                [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub_start")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"⚠️ عذراً {user.first_name}!\n"
                f"يجب عليك الاشتراك في قناتنا أولاً:\n"
                f"{channel}\n\n"
                "بعد الاشتراك اضغط على زر التحقق",
                reply_markup=reply_markup
            )
            return
        
        keyboard = [
            [InlineKeyboardButton("💰 رصيدي", callback_data="balance"),
             InlineKeyboardButton("📈 الإحصائيات", callback_data="stats")],
            [InlineKeyboardButton("🤝 دعوة أصدقاء", callback_data="invite"),
             InlineKeyboardButton("🎁 مكافأة يومية", callback_data="daily_bonus")],
            [InlineKeyboardButton("🎁 كود الهدية", callback_data="enter_gift"),
             InlineKeyboardButton("📢 قناة الاشتراك", callback_data="channels")],
            [InlineKeyboardButton("💳 سحب رصيد", callback_data="withdraw"),
             InlineKeyboardButton("🔄 تحويل رصيد", callback_data="transfer_balance")],
            [InlineKeyboardButton("🛠 الدعم", callback_data="support")]
        ]
        
        if user_id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("🛠 لوحة المطور", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = f"""
🎉 أهلاً بك مجدداً {user.first_name}!

📞 رقمك السوري: {users_data[user_id]['syrian_phone']}
✅ حسابك موثق وهوية سورية مؤكدة

💰 الرصيد: {get_balance(user_id)} ليرة
👥 الإحالات: {users_data[user_id].get('referred_count', 0)}
🔄 رسوم التحويل: {bot_settings['transfer_fee_percent']}%
        """
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
        return ConversationHandler.END
    
    # ✅ التعديل الرئيسي: التحقق من الاشتراك أولاً مباشرة
    is_subscribed, channel = await check_subscription(context, user_id)
    
    if not is_subscribed:
        keyboard = [
            [InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{channel[1:]}")],
            [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub_math")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🔒 نظام الإحالات\n\n"
            f"مرحباً {user.first_name}!\n\n"
            f"📌 هذا البوت مخصص حصرياً للمواطنين السوريين.\n"
            f"🔒 يجب التحقق من رقم هاتفك السوري لاستخدام البوت.\n\n"
            f"🎯 نظام الإحالات:\n"
            f"• تم دعوتك عبر رابط إحالة\n"
            f"• بعد الاشتراك والتحقق، سيحصل صديقك على مكافأة\n\n"
            f"📢 أولاً، يجب عليك الاشتراك في قناتنا:\n"
            f"{channel}\n\n"
            f"بعد الاشتراك اضغط على زر التحقق",
            reply_markup=reply_markup
        )
        
        return CHECK_SUB_BEFORE_MATH
    else:
        keyboard = [
            [KeyboardButton("📱 مشاركة جهة الاتصال", request_contact=True)],
            [KeyboardButton("")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        # ✅ إصلاح: التحقق من وجود رابط إحالة
        referral_message = ""
        if invited_by and invited_by in users_data:
            referral_message = f"\n🎯 تمت دعوتك بواسطة: @{users_data[invited_by].get('username', 'مستخدم')}\nبعد التحقق، سيحصل على مكافأة الإحالة!"
        
        await update.message.reply_text(
          f"🔐 *نظام التحقق الإلزامي*\n\n"
    f"هذا البوت حصري للمواطنين السوريين، الرجاء التحقق من هويتك السورية للمتابعة\n\n"
    f"*كيفية التحقق:*\n"
    f"1. انقر على زر 'مشاركة رقم الهاتف' أدناه\n"
    f"2. سيتم التحقق تلقائياً من رقمك السوري\n\n"
    f"⚠️ *تنبيه هام:*\n"
    f"يمنع كتابة الرقم يدوياً بشكل قطعي\n"
    f"أي محاولة للتحايل ستؤدي إلى حظر نهائي للحساب\n"
    f"الرقم يجب أن يكون سورياً يبدأ بـ 09\n\n"
    f"🔔 *مزايا التحقق:*\n"
    f"وصول كامل لخدمات البوت\n"
    f"مشاركة في نظام المكافآت\n"
    f"تحويلات وسحوبات آمنة\n\n"
    f"للمساعدة @Sports_5K",
            reply_markup=reply_markup
        )
        
        return VERIFY_SYRIAN_PHONE

# التحقق من الاشتراك قبل التسجيل
async def check_sub_math_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    is_subscribed, channel = await check_subscription(context, user_id)
    
    if not is_subscribed:
        keyboard = [
            [InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{channel[1:]}")],
            [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub_math")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"⚠️ يجب عليك الاشتراك في القناة {channel} أولاً!\n"
            "بعد الاشتراك اضغط على زر التحقق",
            reply_markup=reply_markup
        )
        return CHECK_SUB_BEFORE_MATH
    
    keyboard = [
        [KeyboardButton("📱 مشاركة جهة الاتصال", request_contact=True)],
        [KeyboardButton("")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    # ✅ إصلاح: عرض رسالة الإحالة إذا كان دخل من رابط
    referral_message = ""
    invited_by = context.user_data.get('invited_by')
    if invited_by and invited_by in users_data:
        referral_message = f"\n🎯 تمت دعوتك بواسطة: @{users_data[invited_by].get('username', 'مستخدم')}\nبعد التحقق، سيحصل على مكافأة الإحالة!"
    
    await query.edit_message_text(
        f"✅ تم التحقق من الاشتراك بنجاح!\n\n"
        f"🔒 التحقق من الهوية السورية\n\n"
        f"📌 هذا البوت مخصص حصرياً للمواطنين السوريين.\n"
        f"🔐 يجب التحقق من رقم هاتفك السوري لاستخدام البوت.\n"
        f"{referral_message}\n\n"
        f"📱 الرجاء مشاركة رقم هاتفك السوري:\n"
        f"1. اضغط على زر 'مشاركة جهة الاتصال' أدناه\n\n"
        f"⚠️ أي محاولة لكتابة الرقم يدوياً ستؤدي إلى حظر دائم للحساب!",
        reply_markup=reply_markup
    )
    
    return VERIFY_SYRIAN_PHONE

# التحقق من كود التحقق مع إصلاح مشكلة الإحالة
async def verify_code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    try:
        user_code = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال كود التحقق المكون من 6 أرقام. حاول مرة أخرى:")
        return VERIFY_CODE
    
    stored_code = context.user_data.get('verification_code')
    verification_time = context.user_data.get('verification_time')
    clean_phone = context.user_data.get('syrian_phone')
    
    if not stored_code or not verification_time:
        await update.message.reply_text("❌ انتهت صلاحية الكود. الرجاء البدء من جديد باستخدام /start")
        return ConversationHandler.END
    
    if datetime.now() - verification_time > timedelta(minutes=10):
        await update.message.reply_text("❌ انتهت صلاحية الكود. الرجاء البدء من جديد باستخدام /start")
        return ConversationHandler.END
    
    if user_code != stored_code:
        await update.message.reply_text("❌ كود التحقق غير صحيح. حاول مرة أخرى:")
        return VERIFY_CODE
    
    # ✅ إنشاء مسألة رياضية بسيطة
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    math_answer = num1 + num2
    
    # ✅ حفظ الإجابة في context.user_data
    context.user_data['math_answer'] = math_answer
    
    # ✅ إصلاح: استرجاع معلومات الإحالة
    invited_by = context.user_data.get('invited_by')
    
    await update.message.reply_text(
        f"✅ تم التحقق من الكود بنجاح!\n\n"
        f"🎯 نظام الإحالات\n\n"
        f"تم اشتراكك بنجاح!\n\n"
        f"لإكمال عملية الإحالة، يرجى حل المسألة الرياضية التالية:\n\n"
        f"{num1} + {num2} = ?\n\n"
        f"📝 الرجاء إرسال الإجابة فقط (رقم):\n"
        f"❌ للإلغاء، اضغط /cancel"
    )
    
    return VERIFY_MATH

# التحقق من الإجابة الرياضية مع إصلاح مشكلة الإحالة
async def verify_math(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    try:
        user_answer = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال رقم صحيح. حاول مرة أخرى:")
        return VERIFY_MATH
    
    correct_answer = context.user_data.get('math_answer')
    
    if user_answer == correct_answer:
        # ✅ إصلاح المشكلة: استرجاع معلومات الإحالة بشكل آمن
        invited_by = context.user_data.get('invited_by')
        username = context.user_data.get('username')
        first_name = context.user_data.get('first_name')
        last_name = context.user_data.get('last_name')
        phone_number = context.user_data.get('syrian_phone')
        
        welcome_bonus = random.randint(10, 20)
        
        # 📝 إنشاء حساب المستخدم أولاً
        users_data[user_id] = {
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'syrian_phone': phone_number,
            'phone_verified': True,
            'phone_verified_at': datetime.now(),
            'verification_method': 'code_math',
            'balance': welcome_bonus,
            'invited_by': invited_by,
            'join_date': datetime.now(),
            'last_bonus_date': None,
            'total_gift_earned': 0,
            'referred_count': 0,
            'is_active': True
        }
        
        # ✅ إصلاح المشكلة: إعطاء نقاط الإحالة بعد التحقق مباشرة
        if invited_by and invited_by != user_id and invited_by in users_data:
            # تحديث قائمة الإحالات
            if invited_by not in user_referrals:
                user_referrals[invited_by] = []
            
            # التأكد من عدم تكرار الإحالة
            if user_id not in user_referrals[invited_by]:
                user_referrals[invited_by].append(user_id)
                
                # منح نقاط الإحالة للمدعو
                referral_bonus = bot_settings['referral_bonus']
                users_data[invited_by]['balance'] += referral_bonus
                users_data[invited_by]['referred_count'] = len(user_referrals[invited_by])
                
                logger.info(f"✅ منح نقاط الإحالة: المدعو {invited_by} يحصل على {referral_bonus} ليرة بسبب انضمام {user_id}")
                
                # إرسال تقرير الإحالة
                try:
                    await send_referral_report(context, invited_by, user_id, first_name, referral_bonus)
                except Exception as e:
                    logger.error(f"خطأ في إرسال تقرير الإحالة: {e}")
                
                # إرسال إشعار للمدعو
                try:
                    await context.bot.send_message(
                        invited_by,
                        f"🎉 تمت إحالة جديدة!\n\n"
                        f"👤 المستخدم الجديد: @{username if username else first_name}\n"
                        f"📞 الرقم السوري: {phone_number}\n"
                        f"✅ حل المسألة الرياضية بنجاح\n"
                        f"💰 حصلت على مكافأة إحالة: {referral_bonus} ليرة\n"
                        f"💎 رصيدك الحالي: {users_data[invited_by]['balance']} ليرة\n"
                        f"👥 إجمالي إحالاتك: {len(user_referrals[invited_by])}\n\n"
                        f"🎯 استمر في دعوة المزيد من الأصدقاء!"
                    )
                except Exception as e:
                    logger.error(f"❌ خطأ في إرسال إشعار الإحالة: {e}")
            else:
                logger.info(f"⚠️ الإحالة مكررة: المستخدم {user_id} موجود بالفعل في إحالات {invited_by}")
        else:
            logger.info(f"❌ لم يتم منح نقاط الإحالة. invited_by={invited_by}, user_id={user_id}, invited_by in users_data={invited_by in users_data if invited_by else False}")
        
        context.user_data.clear()
        
        # إرسال تقرير مستخدم جديد
        try:
            await send_new_user_report(context, user_id, username, first_name, phone_number)
        except Exception as e:
            logger.error(f"خطأ في إرسال تقرير المستخدم الجديد: {e}")
        
        keyboard = [
            [InlineKeyboardButton("💰 رصيدي", callback_data="balance"),
             InlineKeyboardButton("📈 الإحصائيات", callback_data="stats")],
            [InlineKeyboardButton("🤝 دعوة أصدقاء", callback_data="invite"),
             InlineKeyboardButton("🎁 مكافأة يومية", callback_data="daily_bonus")],
            [InlineKeyboardButton("🎁 كود الهدية", callback_data="enter_gift"),
             InlineKeyboardButton("📢 قناة الاشتراك", callback_data="channels")],
            [InlineKeyboardButton("💳 سحب رصيد", callback_data="withdraw"),
             InlineKeyboardButton("🔄 تحويل رصيد", callback_data="transfer_balance")],
            [InlineKeyboardButton("🛠 الدعم", callback_data="support")]
        ]
        
        if user_id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("🛠 لوحة المطور", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        success_text = f"""
✅ تم التحقق بنجاح!

🎉 مبروك {first_name}!
• تمت إضافتك إلى نظام الإحالات
• رقمك السوري: {phone_number}
• حصلت على مكافأة ترحيبية: {welcome_bonus} ليرة
"""
        
        if invited_by and invited_by in users_data:
            success_text += f"• تمت مكافأة المدعو بمبلغ {bot_settings['referral_bonus']} ليرة\n\n"
            success_text += f"✨ استمتع بميزات البوت السوري الحصري!\n\n"
            success_text += f"🎯 تمت دعوتك بواسطة: @{users_data[invited_by].get('username', 'مستخدم')}"
        else:
            success_text += f"\n✨ استمتع بميزات البوت السوري الحصري!"
        
        await update.message.reply_text(success_text, reply_markup=ReplyKeyboardRemove())
        await update.message.reply_text("🏠 القائمة الرئيسية:", reply_markup=reply_markup)
        
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ الإجابة خاطئة. حاول مرة أخرى:")
        return VERIFY_MATH

# دالة مساعدة للتحقق من صلاحية المستخدم قبل تنفيذ أي أمر
async def require_syrian_verification(user_id, context, update=None, query=None):
    has_access, access_type, message, keyboard = await check_user_access(user_id, context)
    
    if not has_access:
        if access_type == "ممنوع":
            if query:
                if keyboard:
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.edit_message_text(message, reply_markup=reply_markup)
                else:
                    await query.edit_message_text(message)
            elif update:
                if keyboard:
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text(message, reply_markup=reply_markup)
                else:
                    await update.message.reply_text(message)
        else:
            if query:
                await query.edit_message_text(message)
            elif update:
                await update.message.reply_text(message)
        return False
    return True

# معالجة الأزرار
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if query.data.startswith("unban_"):
        if user_id != ADMIN_ID:
            await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
            return
        
        try:
            banned_user_id = int(query.data.split("_")[1])
            if unban_user(banned_user_id):
                await query.edit_message_text(f"✅ تم فك حظر المستخدم {banned_user_id} بنجاح!")
                
                try:
                    await context.bot.send_message(
                        banned_user_id,
                        "🎉 تم فك حظر حسابك!\n\n"
                        "✅ يمكنك الآن استخدام البوت مرة أخرى.\n"
                        "🚀 ابدأ باستخدام /start"
                    )
                except:
                    pass
            else:
                await query.edit_message_text(f"❌ المستخدم {banned_user_id} ليس محظوراً.")
        except:
            await query.edit_message_text("❌ حدث خطأ في فك الحظر.")
        return
    
    if query.data == "reverify_phone":
        if user_id != ADMIN_ID:
            await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
            return
        
        context.user_data.clear()
        context.user_data['user_id'] = user_id
        context.user_data['username'] = query.from_user.username
        context.user_data['first_name'] = query.from_user.first_name
        context.user_data['last_name'] = query.from_user.last_name
        
        keyboard = [
            [KeyboardButton("📱 مشاركة جهة الاتصال", request_contact=True)],
            [KeyboardButton("❌ إلغاء")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        await query.edit_message_text(
            f"🔄 إعادة التحقق من الهوية السورية\n\n"
            f"📱 الرجاء مشاركة رقم هاتفك السوري مرة أخرى:\n"
            f"1. اضغط على زر 'مشاركة جهة الاتصال' أدناه\n"
            f"2. أو أرسل رقمك يدوياً",
            reply_markup=reply_markup
        )
        
        context.user_data['reverify_mode'] = True
        return VERIFY_SYRIAN_PHONE
    
    # التحقق العام للمستخدمين العاديين
    if user_id != ADMIN_ID and not query.data.startswith("check_sub"):
        is_valid, message = await check_subscription_and_verification(user_id, context, callback_query=query)
        if not is_valid:
            return
    
    if query.data == "balance":
        balance = get_balance(user_id)
        await query.edit_message_text(f"💎 رصيدك الحالي: {balance} ليرة")
    
    elif query.data == "daily_bonus":
        is_subscribed, channel = await check_subscription(context, user_id)
        if not is_subscribed:
            keyboard = [
                [InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{channel[1:]}")],
                [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"⚠️ يجب عليك الاشتراك في القناة {channel} أولاً!",
                reply_markup=reply_markup
            )
            return
        
        user_data = users_data.get(user_id)
        if not user_data:
            await query.edit_message_text("❌ لم يتم العثور على بيانات المستخدم.")
            return
        
        today = datetime.now().date()
        last_bonus_date = user_data.get('last_bonus_date')
        
        # التحقق من آخر مكافأة
        if last_bonus_date:
            if isinstance(last_bonus_date, datetime):
                last_date = last_bonus_date.date()
            else:
                try:
                    last_date = datetime.strptime(str(last_bonus_date), '%Y-%m-%d').date()
                except:
                    last_date = None
            
            if last_date == today:
                await query.edit_message_text(
                    "⚠️ لقد حصلت على المكافأة اليوم بالفعل!\n"
                    "⏰ عد غداً للحصول على مكافأة جديدة."
                )
                return
        
        # منح المكافأة
        min_bonus = bot_settings['daily_bonus_min']
        max_bonus = bot_settings['daily_bonus_max']
        bonus = random.randint(min_bonus, max_bonus)
        
        update_balance(user_id, bonus)
        users_data[user_id]['last_bonus_date'] = datetime.now()
        
        await query.edit_message_text(
            f"🎉 مبروك! حصلت على {bonus} ليرة كمكافأة يومية!\n\n"
            f"💰 رصيدك الجديد: {get_balance(user_id)} ليرة"
        )
    
    elif query.data == "invite":
        is_subscribed, channel = await check_subscription(context, user_id)
        if not is_subscribed:
            keyboard = [
                [InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{channel[1:]}")],
                [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"⚠️ يجب عليك الاشتراك في القناة {channel} أولاً!",
                reply_markup=reply_markup
            )
            return
        
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        
        # ✅ إصلاح: عرض عدد الإحالات بشكل صحيح
        referrals_count = users_data[user_id].get('referred_count', 0)
        total_earned = referrals_count * bot_settings['referral_bonus']
        
        invite_text = f"""
🤝 دعوة الأصدقاء

✅ أنت مستخدم سوري موثق:
📞 رقمك: {users_data[user_id]['syrian_phone']}

🔗 رابط الدعوة الخاص بك:
{ref_link}

💰 مكافأة الإحالة: {bot_settings['referral_bonus']} ليرة لكل صديق
👥 عدد أحالتك: {referrals_count} صديق
💎 إجمالي أرباح الإحالة: {total_earned} ليرة

📢 شروط الإحالة:
• يجب أن يكون صديقك سوريًا
• يجب على صديقك التحقق برقم هاتف سوري
• يجب على صديقك حل مسألة رياضية بسيطة
• أنت تحصل على {bot_settings['referral_bonus']} ليرة لكل إحالة

🎯 كلما زاد عدد الأصدقاء الذين تدعوهم، زادت أرباحك!
    """
        await query.edit_message_text(invite_text)
    
    elif query.data == "transfer_balance":
        is_subscribed, channel = await check_subscription(context, user_id)
        if not is_subscribed:
            keyboard = [
                [InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{channel[1:]}")],
                [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"⚠️ يجب عليك الاشتراك في القناة {channel} أولاً!",
                reply_markup=reply_markup
            )
            return
        
        min_transfer = bot_settings['min_transfer']
        fee_percent = bot_settings['transfer_fee_percent']
        balance = get_balance(user_id)
        
        await query.edit_message_text(
            f"🔄 تحويل الرصيد\n\n"
            f"📊 إحصائيات التحويل:\n"
            f"💰 رصيدك الحالي: {balance} ليرة\n"
            f"💸 الحد الأدنى للتحويل: {min_transfer} ليرة\n"
            f"📈 رسوم التحويل: {fee_percent}%\n\n"
            f"🔢 الرجاء إدخال المبلغ الذي تريد تحويله:\n"
            f"❌ للإلغاء، اضغط /cancel"
        )
        
        return TRANSFER_AMOUNT
    
    elif query.data == "enter_gift":
        await enter_gift_code(update, context)
        return ENTER_GIFT_CODE
    
    elif query.data == "create_gift_code":
        if user_id != ADMIN_ID:
            await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
            return ConversationHandler.END
        await create_gift_code(update, context)
        return CREATE_GIFT_CODE
    
    elif query.data == "change_referral_bonus":
        if user_id != ADMIN_ID:
            await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
            return ConversationHandler.END
        await change_referral_bonus(update, context)
        return CHANGE_REFERRAL_BONUS
    
    elif query.data == "change_daily_bonus":
        if user_id != ADMIN_ID:
            await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
            return ConversationHandler.END
        await change_daily_bonus(update, context)
        return CHANGE_DAILY_BONUS
    
    elif query.data == "change_transfer_fee":
        if user_id != ADMIN_ID:
            await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
            return ConversationHandler.END
        await change_transfer_fee(update, context)
        return CHANGE_TRANSFER_FEE
    
    elif query.data == "broadcast_message":
        if user_id != ADMIN_ID:
            await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
            return ConversationHandler.END
        await broadcast_message(update, context)
        return BROADCAST_MESSAGE
    
    elif query.data == "manual_ban_user":
        if user_id != ADMIN_ID:
            await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
            return ConversationHandler.END
        await manual_ban_user_prompt(update, context)
        return MANUAL_BAN_USER
    
    elif query.data == "unban_user_menu":
        if user_id != ADMIN_ID:
            await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
            return ConversationHandler.END
        await unban_user_prompt(update, context)
        return UNBAN_USER
    
    elif query.data == "change_reports_channel":
        if user_id != ADMIN_ID:
            await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
            return ConversationHandler.END
        await change_reports_channel(update, context)
        return CHANGE_REPORTS_CHANNEL
    
    elif query.data == "gift_stats" and user_id == ADMIN_ID:
        total_codes = len(gift_codes)
        active_codes = sum(1 for code in gift_codes.values() if code['is_active'])
        total_amount = sum(code['amount'] for code in gift_codes.values())
        
        total_used = 0
        total_redeemed = 0
        for user_codes in used_gift_codes.values():
            total_used += len(user_codes)
            for code in user_codes:
                if code in gift_codes:
                    total_redeemed += gift_codes[code]['amount']
        
        recent_codes = sorted(gift_codes.items(), key=lambda x: x[1]['created_at'], reverse=True)[:5]
        
        gift_stats = f"""
📊 إحصائيات أكواد الهدايا

📈 إحصائيات عامة:
🎁 إجمالي الأكواد: {total_codes}
✅ الأكواد النشطة: {active_codes}
💰 إجمالي القيمة: {total_amount} ليرة
🎯 تم الاستخدام: {total_used} مرة
💸 إجمالي المبالغ المستردة: {total_redeemed} ليرة

📋 آخر 5 أكواد تم إنشاؤها:
"""
        for i, (code, data) in enumerate(recent_codes, 1):
            gift_stats += f"{i}. `{code}` - {data['amount']} ليرة (استخدم {data['used_count']}/{data['max_uses']})\n"
        
        await query.edit_message_text(gift_stats)
    
    elif query.data == "check_sub" or query.data == "check_sub_start":
        is_subscribed, channel = await check_subscription(context, user_id)
        
        if is_subscribed:
            if query.data == "check_sub_start":
                if not is_user_syrian(user_id):
                    await query.edit_message_text("❌ يجب التحقق من هويتك السورية أولاً.\nاستخدم /start للبدء.")
                    return
                
                user = query.from_user
                keyboard = [
                    [InlineKeyboardButton("💰 رصيدي", callback_data="balance"),
                     InlineKeyboardButton("📈 الإحصائيات", callback_data="stats")],
                    [InlineKeyboardButton("🤝 دعوة أصدقاء", callback_data="invite"),
                     InlineKeyboardButton("🎁 مكافأة يومية", callback_data="daily_bonus")],
                    [InlineKeyboardButton("🎁 كود الهدية", callback_data="enter_gift"),
                     InlineKeyboardButton("📢 قناة الاشتراك", callback_data="channels")],
                    [InlineKeyboardButton("💳 سحب رصيد", callback_data="withdraw"),
                     InlineKeyboardButton("🔄 تحويل رصيد", callback_data="transfer_balance")],
                    [InlineKeyboardButton("🛠 الدعم", callback_data="support")]
                ]
                
                if user_id == ADMIN_ID:
                    keyboard.append([InlineKeyboardButton("🛠 لوحة المطور", callback_data="admin_panel")])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                welcome_text = f"""
🎉 أهلاً بك {user.first_name} في البوت!

✅ أنت مستخدم سوري موثق:
📞 رقم الهاتف: {users_data[user_id]['syrian_phone']}

💰 الرصيد: {get_balance(user_id)} ليرة
👥 الإحالات: {users_data[user_id].get('referred_count', 0)}
🔄 رسوم التحويل: {bot_settings['transfer_fee_percent']}%
                """
                
                await query.edit_message_text(welcome_text, reply_markup=reply_markup)
            else:
                await query.edit_message_text("✅ أنت مشترك في القناة المطلوبة!")
        else:
            keyboard = [
                [InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{channel[1:]}")],
                [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"⚠️ يجب عليك الاشتراك في القناة {channel} أولاً!\n"
                "بعد الاشتراك اضغط على زر التحقق",
                reply_markup=reply_markup
            )
    
    elif query.data == "check_sub_math":
        await check_sub_math_callback(update, context)
    
    elif query.data == "support":
        support_text = """
🛠 مركز الدعم والفريق

📞 للاستفسارات والدعم الفني:
https://t.me/Sports_5K

📢 قناة البوت الرسمية:
https://t.me/One_Dot_1bot

🎁 للحصول على أكواد هدايا مجانية:
https://t.me/One_Dot_1bot

⚠️ احذر من المحتالين، لا يوجد ممثلون رسميون للبوت خارج هذه القنوات.
        """
        await query.edit_message_text(support_text)
    
    elif query.data == "withdraw":
        is_subscribed, channel = await check_subscription(context, user_id)
        if not is_subscribed:
            keyboard = [
                [InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{channel[1:]}")],
                [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"⚠️ يجب عليك الاشتراك في القناة {channel} أولاً!",
                reply_markup=reply_markup
            )
            return
        
        balance = get_balance(user_id)
        min_withdraw = bot_settings['min_withdraw']
        
        if balance < min_withdraw:
            await query.edit_message_text(
                f"⚠️ الحد الأدنى للسحب هو {min_withdraw} ليرة\n"
                f"💰 رصيدك الحالي: {balance} ليرة\n\n"
                f"تحتاج إلى {min_withdraw - balance} ليرة إضافية للسحب."
            )
            return
        
        keyboard = [
            [InlineKeyboardButton("📱 سريتيل كاش", callback_data="withdraw_syriatel_cash")],
            [InlineKeyboardButton("💳 شام كاش سوري", callback_data="withdraw_sham_cash_syr")],
            [InlineKeyboardButton("💵 شام كاش دولار", callback_data="withdraw_sham_cash_usd")],
            [InlineKeyboardButton("🏦 Paynes", callback_data="withdraw_paynes")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"💳 اختر طريقة السحب:\n\n"
            f"✅ أنت مستخدم سوري موثق\n"
            f"📞 رقمك: {users_data[user_id]['syrian_phone']}\n"
            f"💰 رصيدك: {balance} ليرة\n"
            f"💸 الحد الأدنى للسحب: {min_withdraw} ليرة",
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("withdraw_"):
        await handle_withdraw_method(update, context)
        return WITHDRAW_AMOUNT
    
    elif query.data == "confirm_withdraw":
        await confirm_withdraw(update, context)
    
    elif query.data == "cancel_withdraw":
        await cancel_withdraw(update, context)
    
    elif query.data == "confirm_transfer":
        await confirm_transfer(update, context)
    
    elif query.data == "cancel_transfer":
        await cancel_transfer(update, context)
    
    elif query.data == "stats":
        is_subscribed, channel = await check_subscription(context, user_id)
        if not is_subscribed:
            keyboard = [
                [InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{channel[1:]}")],
                [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"⚠️ يجب عليك الاشتراك في القناة {channel} أولاً!",
                reply_markup=reply_markup
            )
            return
        
        balance = get_balance(user_id)
        referrals_count = len(user_referrals.get(user_id, []))
        
        user_data = users_data.get(user_id, {})
        user_gift_earned = user_data.get('total_gift_earned', 0)
        
        total_users = len(users_data)
        total_referrals = sum(len(refs) for refs in user_referrals.values())
        total_balance = sum(user['balance'] for user in users_data.values())
        
        total_withdrawals = 0
        for w in withdrawals_data.values():
            if w['status'] == 'completed':
                total_withdrawals += w['amount']
        
        total_gift_codes_used = 0
        for user_codes in used_gift_codes.values():
            total_gift_codes_used += len(user_codes)
        
        stats_text = f"""
📊 إحصائيات البوت

👤 إحصائياتك الشخصية:
✅ مستخدم سوري موثق
📞 رقم الهاتف: {user_data.get('syrian_phone', 'غير متوفر')}
💰 رصيدك: {balance} ليرة
👥 عدد أحالتك: {referrals_count} صديق
🎁 إجمالي الهدايا المستلمة: {user_gift_earned} ليرة

🌍 إحصائيات عامة:
👥 إجمالي المستخدمين السوريين: {total_users}
📤 إجمالي الإحالات: {total_referrals}
💰 إجمالي الرصيد: {total_balance} ليرة
💸 إجمالي المسحوبات: {total_withdrawals} ليرة
🎁 أكواد الهدايا المستخدمة: {total_gift_codes_used}
⛔ عدد المستخدمين الممنوعين: {len(banned_users)}
🔄 عدد عمليات التحويل: {len(transfer_logs)}

🎯 مكافأة الإحالة: {bot_settings['referral_bonus']} ليرة
💸 الحد الأدنى للسحب: {bot_settings['min_withdraw']} ليرة
🔄 رسوم التحويل: {bot_settings['transfer_fee_percent']}%
        """
        await query.edit_message_text(stats_text)
    
    elif query.data == "channels":
        channel = REQUIRED_CHANNELS[0]
        channels_text = f"📢 قناة الاشتراك الإلزامية:\n\n• {channel['username']}\n\n⚠️ يجب الاشتراك في هذه القناة للاستفادة من جميع ميزات البوت"
        
        keyboard = [[InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(channels_text, reply_markup=reply_markup)
    
    elif query.data == "admin_panel" and user_id == ADMIN_ID:
        await show_admin_panel(user_id, context)
    
    elif query.data == "change_min_withdraw" and user_id == ADMIN_ID:
        await change_min_withdraw(update, context)
        return CHANGE_MIN_WITHDRAW
    
    elif query.data == "detailed_stats" and user_id == ADMIN_ID:
        total_users = len(users_data)
        total_referrals = sum(len(refs) for refs in user_referrals.values())
        total_balance = sum(user['balance'] for user in users_data.values())
        
        # ✅ إحصاءات الإحالات
        referral_stats = {}
        for uid, refs in user_referrals.items():
            if uid in users_data:
                username = users_data[uid].get('username', 'مجهول')
                referral_stats[username] = len(refs)
        
        top_referrers = sorted(referral_stats.items(), key=lambda x: x[1], reverse=True)[:5]
        
        today = datetime.now().date()
        today_users = 0
        for user_data in users_data.values():
            join_date = user_data.get('join_date')
            if isinstance(join_date, datetime) and join_date.date() == today:
                today_users += 1
        
        top_users = []
        for uid, data in users_data.items():
            top_users.append((data.get('username', 'مجهول'), data['balance'], data.get('syrian_phone', 'غير معروف')))
        top_users.sort(key=lambda x: x[1], reverse=True)
        top_users = top_users[:5]
        
        top_users_text = "\n🏆 أعلى 5 مستخدمين حسب الرصيد:\n"
        for i, (username, balance, phone) in enumerate(top_users, 1):
            top_users_text += f"{i}. @{username}: {balance} ليرة - {phone}\n"
        
        top_referrers_text = "\n🏆 أعلى 5 مدعين:\n"
        for i, (username, ref_count) in enumerate(top_referrers, 1):
            top_referrers_text += f"{i}. @{username}: {ref_count} إحالة\n"
        
        detailed_stats = f"""
📊 إحصائيات مفصلة

👥 إجمالي المستخدمين السوريين: {total_users}
📤 إجمالي الإحالات: {total_referrals}
💰 إجمالي الرصيد: {total_balance} ليـرة
⛔ عدد الممنوعين: {len(banned_users)}
🔄 عدد عمليات التحويل: {len(transfer_logs)}

📈 مستخدمين اليوم: {today_users}
📅 التاريخ: {today}
⏰ الوقت: {datetime.now().strftime("%H:%M:%S")}
{top_users_text}
{top_referrers_text}
        """
        
        await query.edit_message_text(detailed_stats)
    
    elif query.data == "user_list" and user_id == ADMIN_ID:
        sorted_users = sorted(users_data.items(), key=lambda x: x[1].get('join_date', datetime.now()), reverse=True)[:10]
        
        users_text = "👥 آخر 10 مستخدمين سوريين:\n\n"
        for uid, data in sorted_users:
            username = data.get('username', 'مجهول')
            balance = data.get('balance', 0)
            phone = data.get('syrian_phone', 'غير معروف')
            join_date = data.get('join_date', datetime.now())
            if isinstance(join_date, datetime):
                join_date_str = join_date.strftime('%Y-%m-%d')
            else:
                join_date_str = str(join_date)
            
            referred_by = ""
            if data.get('invited_by'):
                referred_by = f"👤 دعا بواسطة: {data['invited_by']}\n"
            
            users_text += f"🆔 {uid}\n👤 @{username}\n📞 {phone}\n💰 {balance} ليرة\n{referred_by}📅 {join_date_str}\n"
            users_text += "─" * 20 + "\n"
        
        await query.edit_message_text(users_text)
    
    elif query.data == "withdrawal_requests" and user_id == ADMIN_ID:
        pending_withdrawals = {wid: w for wid, w in withdrawals_data.items() if w['status'] == 'pending'}
        
        if not pending_withdrawals:
            await query.edit_message_text("✅ لا توجد طلبات سحب معلقة حالياً.")
            return
        
        withdrawal_text = "⏳ طلبات السحب المعلقة:\n\n"
        for i, (wid, w) in enumerate(pending_withdrawals.items(), 1):
            user_id_withdraw = w['user_id']
            user_data = users_data.get(user_id_withdraw, {})
            first_name = user_data.get('first_name', 'مجهول')
            username = user_data.get('username', 'لا يوجد')
            phone = user_data.get('syrian_phone', 'غير معروف')
            amount = w['amount']
            method = w['method']
            receiver_info = w['receiver_info']
            
            method_info = WITHDRAWAL_METHODS.get(method, {"name": "غير معروف"})
            method_name = method_info['name']
            
            if method == "syriatel_cash":
                details = f"📱 رقم الهاتف: {receiver_info}"
            elif method in ["sham_cash_syr", "sham_cash_usd"]:
                details = f"📍 العنوان: {receiver_info}"
            elif method == "paynes":
                details = f"🏦 الحساب/العنوان: {receiver_info}"
            else:
                details = f"📋 التفاصيل: {receiver_info}"
            
            withdrawal_text += f"{i}. {first_name} (@{username})\n"
            withdrawal_text += f"   📞 {phone}\n"
            withdrawal_text += f"   💰 {amount} ليرة | 💳 {method_name}\n"
            withdrawal_text += f"   {details}\n"
            withdrawal_text += f"   📅 {w['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
            withdrawal_text += f"   ⚡ معالجة: /process_{wid}\n"
            withdrawal_text += "─" * 30 + "\n"
        
        withdrawal_text += "\n📝 استخدم /process_رقم_المعرف لمعالجة الطلب"
        
        await query.edit_message_text(withdrawal_text)
    
    elif query.data == "refresh_stats" and user_id == ADMIN_ID:
        await show_admin_panel(user_id, context)
    
    elif query.data == "back_to_main":
        keyboard = [
            [InlineKeyboardButton("💰 رصيدي", callback_data="balance"),
             InlineKeyboardButton("📈 الإحصائيات", callback_data="stats")],
            [InlineKeyboardButton("🤝 دعوة أصدقاء", callback_data="invite"),
             InlineKeyboardButton("🎁 مكافأة يومية", callback_data="daily_bonus")],
            [InlineKeyboardButton("🎁 كود الهدية", callback_data="enter_gift"),
             InlineKeyboardButton("📢 قناة الاشتراك", callback_data="channels")],
            [InlineKeyboardButton("💳 سحب رصيد", callback_data="withdraw"),
             InlineKeyboardButton("🔄 تحويل رصيد", callback_data="transfer_balance")],
            [InlineKeyboardButton("🛠 الدعم", callback_data="support")]
        ]
        
        if user_id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("🛠 لوحة المطور", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🏠 القائمة الرئيسية", reply_markup=reply_markup)
    
    elif query.data == "cancel":
        await cancel(update, context)

# إدخال كود الهدية
async def enter_gift_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if not await require_syrian_verification(user_id, context, query=query):
        return ConversationHandler.END
    
    is_subscribed, channel = await check_subscription(context, user_id)
    if not is_subscribed:
        keyboard = [
            [InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{channel[1:]}")],
            [InlineKeyboardButton("🔄 تحقق من الاشتراك", callback_data="check_sub")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"⚠️ يجب عليك الاشتراك في القناة {channel} أولاً!",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    
    await query.edit_message_text(
        "🎁 نظام أكواد الهدايا\n\n"
        "🔢 الرجاء إدخال كود الهدية الذي لديك:\n\n"
        "📝 ملاحظة: يمكن استخدام كل كود مرة واحدة فقط\n"
        "🚫 أرسل الكود في رسالة واحدة فقط\n"
        "❌ للإلغاء، اضغط /cancel"
    )
    
    return ENTER_GIFT_CODE

# التحقق من كود الهدية
async def verify_gift_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if not await require_syrian_verification(user_id, context, update=update):
        return ConversationHandler.END
    
    # التحقق من الاشتراك
    is_subscribed, channel = await check_subscription(context, user_id)
    if not is_subscribed:
        await update.message.reply_text(
            f"⚠️ يجب عليك الاشتراك في القناة {channel} أولاً!"
        )
        return ConversationHandler.END
    
    gift_code = update.message.text.strip().upper()
    
    if len(gift_code) < 3:
        await update.message.reply_text("❌ كود الهدية قصير جداً.")
        return ConversationHandler.END
    
    # التحقق من كود الهدية
    if gift_code not in gift_codes:
        await update.message.reply_text("❌ كود الهدية غير صحيح أو غير موجود.")
        return ConversationHandler.END
    
    code_data = gift_codes[gift_code]
    
    # التحقق من صلاحية الكود
    if not code_data.get('is_active', True):
        await update.message.reply_text("❌ كود الهدية غير مفعل.")
        return ConversationHandler.END
    
    # التحقق من تاريخ الانتهاء
    expires_at = code_data.get('expires_at')
    if expires_at and expires_at < datetime.now():
        await update.message.reply_text("❌ كود الهدية منتهي الصلاحية.")
        return ConversationHandler.END
    
    # التحقق من عدد الاستخدامات
    max_uses = code_data.get('max_uses', 1)
    used_count = code_data.get('used_count', 0)
    if used_count >= max_uses:
        await update.message.reply_text("❌ تم استخدام كود الهدية بالكامل.")
        return ConversationHandler.END
    
    # التحقق إذا كان المستخدم قد استخدم الكود من قبل
    if user_id in used_gift_codes and gift_code in used_gift_codes[user_id]:
        await update.message.reply_text("❌ لقد استخدمت هذا الكود من قبل.")
        return ConversationHandler.END
    
    # منح المكافأة
    amount = code_data['amount']
    update_balance(user_id, amount)
    
    # تحديث استخدامات الكود
    code_data['used_count'] = used_count + 1
    
    # تسجيل استخدام المستخدم للكود
    if user_id not in used_gift_codes:
        used_gift_codes[user_id] = []
    used_gift_codes[user_id].append(gift_code)
    
    # إرسال تقرير
    try:
        await send_gift_code_report(context, user_id, gift_code, amount)
    except Exception as e:
        logger.error(f"خطأ في إرسال تقرير كود الهدية: {e}")
    
    keyboard = [
        [InlineKeyboardButton("💰 رصيدي", callback_data="balance"),
         InlineKeyboardButton("📈 الإحصائيات", callback_data="stats")],
        [InlineKeyboardButton("🤝 دعوة أصدقاء", callback_data="invite"),
         InlineKeyboardButton("🎁 مكافأة يومية", callback_data="daily_bonus")],
        [InlineKeyboardButton("🎁 كود الهدية", callback_data="enter_gift"),
         InlineKeyboardButton("📢 قناة الاشتراك", callback_data="channels")],
        [InlineKeyboardButton("💳 سحب رصيد", callback_data="withdraw"),
         InlineKeyboardButton("🔄 تحويل رصيد", callback_data="transfer_balance")],
        [InlineKeyboardButton("🛠 الدعم", callback_data="support")]
    ]
    
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🛠 لوحة المطور", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ تم تفعيل كود الهدية بنجاح!\n\n"
        f"🎁 الكود: {gift_code}\n"
        f"💰 المكافأة: {amount} ليرة\n"
        f"💎 رصيدك الجديد: {get_balance(user_id)} ليرة",
        reply_markup=reply_markup
    )
    
    return ConversationHandler.END

# إنشاء كود هدية جديد (للمطور)
async def create_gift_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if user_id != ADMIN_ID:
        await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    await query.edit_message_text(
        "🎁 إنشاء كود هدية جديد\n\n"
        "🔢 الرجاء إدخال المبلغ الذي تريد وضعه في كود الهدية (بالليرة):\n\n"
        f"📊 الحد الأدنى: {bot_settings['gift_code_min']} ليرة\n"
        f"📈 الحد الأقصى: {bot_settings['gift_code_max']} ليرة\n"
        "❌ للإلغاء، اضغط /cancel"
    )
    
    return CREATE_GIFT_CODE

# معالجة إنشاء كود الهدية
async def handle_create_gift_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    try:
        amount = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال رقم صحيح. حاول مرة أخرى:")
        return CREATE_GIFT_CODE
    
    min_amount = bot_settings['gift_code_min']
    max_amount = bot_settings['gift_code_max']
    
    if amount < min_amount:
        await update.message.reply_text(f"❌ المبلغ أقل من الحد الأدنى ({min_amount} ليرة). حاول مرة أخرى:")
        return CREATE_GIFT_CODE
    
    if amount > max_amount:
        await update.message.reply_text(f"❌ المبلغ أكبر من الحد الأقصى ({max_amount} ليرة). حاول مرة أخرى:")
        return CREATE_GIFT_CODE
    
    code = generate_gift_code()
    
    while code in gift_codes:
        code = generate_gift_code()
    
    expiry_days = bot_settings['gift_code_expiry_days']
    expires_at = datetime.now() + timedelta(days=expiry_days)
    
    gift_codes[code] = {
        'amount': amount,
        'created_by': user_id,
        'created_at': datetime.now(),
        'expires_at': expires_at,
        'max_uses': 1,
        'used_count': 0,
        'is_active': True
    }
    
    await update.message.reply_text(
        f"✅ تم إنشاء كود الهدية بنجاح!\n\n"
        f"📋 تفاصيل الكود:\n"
        f"🎁 كود الهدية: `{code}`\n"
        f"💰 المبلغ: {amount} ليرة\n"
        f"📅 تاريخ الإنشاء: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"⏰ تاريخ الانتهاء: {expires_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"🔢 عدد الاستخدامات: 1 مرة\n\n"
        f"📢 يمكنك مشاركة هذا الكود مع المستخدمين!"
    )
    
    return ConversationHandler.END

# تغيير مكافأة الإحالة
async def change_referral_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if user_id != ADMIN_ID:
        await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    current_bonus = bot_settings['referral_bonus']
    
    await query.edit_message_text(
        f"🤝 المكافأة الحالية للإحالة: {current_bonus} ليرة\n\n"
        f"🔢 الرجاء إدخال المكافأة الجديدة للإحالة (بالليرة):\n"
        "❌ للإلغاء، اضغط /cancel"
    )
    
    return CHANGE_REFERRAL_BONUS

# معالجة تغيير مكافأة الإحالة
async def handle_change_referral_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    try:
        new_bonus = int(update.message.text.strip())
        
        if new_bonus <= 0:
            await update.message.reply_text("❌ الرقم يجب أن يكون أكبر من صفر. حاول مرة أخرى:")
            return CHANGE_REFERRAL_BONUS
        
        bot_settings['referral_bonus'] = new_bonus
        
        await update.message.reply_text(f"✅ تم تحديث مكافأة الإحالة إلى {new_bonus} ليرة")
        
        await show_admin_panel(user_id, context)
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال رقم صحيح. حاول مرة أخرى:")
        return CHANGE_REFERRAL_BONUS

# تغيير المكافأة اليومية
async def change_daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if user_id != ADMIN_ID:
        await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    current_min = bot_settings['daily_bonus_min']
    current_max = bot_settings['daily_bonus_max']
    
    await query.edit_message_text(
        f"🎁 المكافأة اليومية الحالية: من {current_min} إلى {current_max} ليرة\n\n"
        f"🔢 الرجاء إدخال الحد الأدنى الجديد للمكافأة اليومية (بالليرة):\n"
        "❌ للإلغاء، اضغط /cancel"
    )
    
    return CHANGE_DAILY_BONUS

# معالجة تغيير المكافأة اليومية
async def handle_change_daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    try:
        new_min = int(update.message.text.strip())
        
        if new_min <= 0:
            await update.message.reply_text("❌ الرقم يجب أن يكون أكبر من صفر. حاول مرة أخرى:")
            return CHANGE_DAILY_BONUS
        
        context.user_data['new_daily_min'] = new_min
        await update.message.reply_text(
            f"✅ تم تعيين الحد الأدنى إلى {new_min} ليرة\n\n"
            f"🔢 الرجاء إدخال الحد الأقصى الجديد للمكافأة اليومية (بالليرة):\n"
            "❌ للإلغاء، اضغط /cancel"
        )
        
        return CHANGE_DAILY_BONUS + 1
        
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال رقم صحيح. حاول مرة أخرى:")
        return CHANGE_DAILY_BONUS

# معالجة الحد الأقصى للمكافأة اليومية
async def handle_change_daily_bonus_max(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    try:
        new_max = int(update.message.text.strip())
        new_min = context.user_data.get('new_daily_min', bot_settings['daily_bonus_min'])
        
        if new_max <= new_min:
            await update.message.reply_text(f"❌ الحد الأقصى يجب أن يكون أكبر من الحد الأدنى ({new_min}). حاول مرة أخرى:")
            return CHANGE_DAILY_BONUS + 1
        
        bot_settings['daily_bonus_min'] = new_min
        bot_settings['daily_bonus_max'] = new_max
        
        context.user_data.pop('new_daily_min', None)
        
        await update.message.reply_text(f"✅ تم تحديث المكافأة اليومية إلى: من {new_min} إلى {new_max} ليرة")
        
        await show_admin_panel(user_id, context)
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال رقم صحيح. حاول مرة أخرى:")
        return CHANGE_DAILY_BONUS + 1

# تغيير نسبة رسوم التحويل
async def change_transfer_fee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if user_id != ADMIN_ID:
        await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    current_fee = bot_settings['transfer_fee_percent']
    
    await query.edit_message_text(
        f"🔄 النسبة الحالية لرسوم التحويل: {current_fee}%\n\n"
        f"🔢 الرجاء إدخال النسبة الجديدة لرسوم التحويل (بالمئة):\n"
        "❌ للإلغاء، اضغط /cancel"
    )
    
    return CHANGE_TRANSFER_FEE

# معالجة تغيير نسبة رسوم التحويل
async def handle_change_transfer_fee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    try:
        new_fee = int(update.message.text.strip())
        
        if new_fee < 0 or new_fee > 100:
            await update.message.reply_text("❌ النسبة يجب أن تكون بين 0 و 100. حاول مرة أخرى:")
            return CHANGE_TRANSFER_FEE
        
        bot_settings['transfer_fee_percent'] = new_fee
        
        await update.message.reply_text(f"✅ تم تحديث نسبة رسوم التحويل إلى {new_fee}%")
        
        await show_admin_panel(user_id, context)
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال رقم صحيح. حاول مرة أخرى:")
        return CHANGE_TRANSFER_FEE

# البث لجميع المستخدمين
async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if user_id != ADMIN_ID:
        await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    await query.edit_message_text(
        "📢 البث لجميع المستخدمين\n\n"
        "🔤 الرجاء إدخال الرسالة التي تريد بثها لجميع المستخدمين:\n\n"
        "📝 يمكنك استخدام التنسيقات التالية:\n"
        "• النصوص العادية\n"
        "• الرموز التعبيرية 🎉\n"
        "• الروابط\n\n"
        "❌ للإلغاء، اضغط /cancel"
    )
    
    return BROADCAST_MESSAGE

# معالجة رسالة البث
async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    message = update.message.text
    total_users = len(users_data)
    
    if total_users == 0:
        await update.message.reply_text("❌ لا يوجد مستخدمين في النظام.")
        return ConversationHandler.END
    
    await update.message.reply_text(f"📤 جاري إرسال الرسالة إلى {total_users} مستخدم...")
    
    success = 0
    failed = 0
    
    for uid in users_data.keys():
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"📢 إشعار من الإدارة:\n\n{message}\n\n"
                     f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            success += 1
        except:
            failed += 1
    
    report = f"""
✅ تم الانتهاء من عملية البث:

📊 النتائج:
• ✅ نجح: {success} مستخدم
• ❌ فشل: {failed} مستخدم
• 📊 الإجمالي: {total_users} مستخدم

⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    await update.message.reply_text(report)
    
    await show_admin_panel(user_id, context)
    
    return ConversationHandler.END

# حظر مستخدم يدويًا
async def manual_ban_user_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if user_id != ADMIN_ID:
        await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    await query.edit_message_text(
        "⛔ حظر مستخدم يدويًا\n\n"
        "🆔 الرجاء إدخال معرف المستخدم الذي تريد حظره:\n"
        "❌ للإلغاء، اضغط /cancel"
    )
    
    return MANUAL_BAN_USER

# معالجة حظر المستخدم يدويًا
async def handle_manual_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    try:
        banned_user_id = int(update.message.text.strip())
        
        context.user_data['manual_ban_user_id'] = banned_user_id
        
        await update.message.reply_text(
            f"🆔 تم تحديد المستخدم: {banned_user_id}\n\n"
            f"📝 الرجاء إدخال سبب الحظر:\n"
            f"❌ للإلغاء، اضغط /cancel"
        )
        
        return MANUAL_BAN_USER + 1
        
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال معرف مستخدم صحيح. حاول مرة أخرى:")
        return MANUAL_BAN_USER

# معالجة سبب الحظر
async def handle_manual_ban_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    reason = update.message.text.strip()
    banned_user_id = context.user_data.get('manual_ban_user_id')
    
    if not banned_user_id:
        await update.message.reply_text("❌ حدث خطأ. الرجاء المحاولة مرة أخرى.")
        return ConversationHandler.END
    
    manual_ban_user(banned_user_id, reason, user_id)
    
    context.user_data.pop('manual_ban_user_id', None)
    
    try:
        await context.bot.send_message(
            banned_user_id,
            f"⛔ تم حظر حسابك!\n\n"
            f"🚫 السبب: {reason}\n"
            f"👤 تم الحظر بواسطة: المطور\n"
            f"📅 تاريخ الحظر: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"📞 للاستفسار: @Sports_5K"
        )
    except:
        pass
    
    await update.message.reply_text(f"✅ تم حظر المستخدم {banned_user_id} بنجاح!\n🚫 السبب: {reason}")
    
    await show_admin_panel(user_id, context)
    
    return ConversationHandler.END

# فك حظر مستخدم
async def unban_user_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if user_id != ADMIN_ID:
        await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    if not banned_users:
        await query.edit_message_text("✅ لا يوجد مستخدمين محظورين حالياً.")
        return ConversationHandler.END
    
    banned_list = "⛔ قائمة المستخدمين المحظورين:\n\n"
    keyboard = []
    
    for i, (uid, ban_info) in enumerate(banned_users.items(), 1):
        reason = ban_info.get('reason', 'غير محدد')
        banned_by = ban_info.get('banned_by', 'النظام')
        banned_at = ban_info.get('banned_at', datetime.now())
        
        user_data = None
        if uid in users_data:
            user_data = users_data[uid]
        elif 'syrian_phone' in ban_info:
            phone = ban_info['syrian_phone']
        else:
            phone = 'غير معروف'
        
        username = user_data.get('username', 'مجهول') if user_data else 'مجهول'
        first_name = user_data.get('first_name', 'مجهول') if user_data else 'مجهول'
        
        banned_list += f"{i}. {first_name} (@{username})\n"
        banned_list += f"   🆔 المعرف: {uid}\n"
        banned_list += f"   🚫 السبب: {reason}\n"
        banned_list += f"   👤 حظر بواسطة: {banned_by}\n"
        banned_list += f"   📅 التاريخ: {banned_at.strftime('%Y-%m-%d %H:%M')}\n"
        banned_list += f"   🔓 فك الحظر: /unban_{uid}\n\n"
        
        keyboard.append([InlineKeyboardButton(f"🔓 {first_name} (@{username})", callback_data=f"unban_{uid}")])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(banned_list, reply_markup=reply_markup)
    
    return ConversationHandler.END

# تغيير قناة التقارير
async def change_reports_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if user_id != ADMIN_ID:
        await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    global REPORTS_CHANNEL
    current_channel = REPORTS_CHANNEL
    
    await query.edit_message_text(
        f"📢 تغيير قناة التقارير\n\n"
        f"📋 القناة الحالية: {current_channel}\n\n"
        f"🔤 الرجاء إرسال معرف القناة الجديدة (يجب أن تبدأ ب @):\n"
        f"مثال: @AL_STORE_REPORTS\n\n"
        f"❌ للإلغاء، اضغط /cancel"
    )
    
    return CHANGE_REPORTS_CHANNEL

# معالجة تغيير قناة التقارير
async def handle_change_reports_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global REPORTS_CHANNEL
    user = update.effective_user
    user_id = user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    new_channel = update.message.text.strip()
    
    if not new_channel.startswith('@'):
        await update.message.reply_text("❌ يجب أن يبدأ معرف القناة ب @. حاول مرة أخرى:")
        return CHANGE_REPORTS_CHANNEL
    
    if len(new_channel) < 5:
        await update.message.reply_text("❌ معرف القناة قصير جداً. حاول مرة أخرى:")
        return CHANGE_REPORTS_CHANNEL
    
    REPORTS_CHANNEL = new_channel
    
    # إرسال تقرير تغيير القناة
    try:
        await context.bot.send_message(
            REPORTS_CHANNEL,
            f"📢 قناة التقارير تم تغييرها\n\n"
            f"✅ تم تغيير قناة التقارير إلى:\n"
            f"📋 {new_channel}\n\n"
            f"👤 تم التغيير بواسطة: {user.first_name}\n"
            f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال إشعار تغيير القناة: {e}")
        await update.message.reply_text(f"⚠️ تم تغيير القناة لكن حدث خطأ في الإرسال: {e}")
    
    await update.message.reply_text(f"✅ تم تغيير قناة التقارير إلى: {new_channel}")
    
    await show_admin_panel(user_id, context)
    
    return ConversationHandler.END

# معالجة تحويل الرصيد
async def handle_transfer_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if not await require_syrian_verification(user_id, context, update=update):
        return ConversationHandler.END
    
    try:
        amount = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال رقم صحيح. حاول مرة أخرى:")
        return TRANSFER_AMOUNT
    
    min_transfer = bot_settings['min_transfer']
    balance = get_balance(user_id)
    
    if amount < min_transfer:
        await update.message.reply_text(
            f"⚠️ الحد الأدنى للتحويل هو {min_transfer} ليرة\n"
            f"💰 رصيدك الحالي: {balance} ليرة\n\n"
            f"تحتاج إلى {min_transfer - amount} ليرة إضافية للسحب.\n\n"
            f"🔢 الرجاء إدخال مبلغ جديد:\n"
            "❌ للإلغاء، اضغط /cancel"
        )
        return TRANSFER_AMOUNT
    
    if amount > balance:
        await update.message.reply_text(
            f"❌ المبلغ أكبر من رصيدك المتاح\n"
            f"💰 الرصيد الحالي: {balance} ليرة\n\n"
            f"🔢 الرجاء إدخال مبلغ أقل أو يساوي رصيدك:\n"
            "❌ للإلغاء، اضغط /cancel"
        )
        return TRANSFER_AMOUNT
    
    context.user_data['transfer_amount'] = amount
    
    await update.message.reply_text(
        f"🔄 تحويل الرصيد\n\n"
        f"💰 المبلغ: {amount} ليرة\n"
        f"📈 رسوم التحويل: {bot_settings['transfer_fee_percent']}%\n"
        f"💸 الرسوم: {(amount * bot_settings['transfer_fee_percent']) / 100} ليرة\n"
        f"✅ المبلغ الصافي: {amount - ((amount * bot_settings['transfer_fee_percent']) / 100)} ليرة\n\n"
        f"🆔 الرجاء إدخال معرف المستلم:\n"
        f"❌ للإلغاء، اضغط /cancel"
    )
    
    return TRANSFER_USER

# معالجة معرف المستلم
async def handle_transfer_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if not await require_syrian_verification(user_id, context, update=update):
        return ConversationHandler.END
    
    receiver_input = update.message.text.strip()
    
    try:
        receiver_id = int(receiver_input)
    except ValueError:
        receiver_id = None
        for uid, user_data in users_data.items():
            username = user_data.get('username', '').lower()
            first_name = user_data.get('first_name', '').lower()
            
            if (receiver_input.lower() == username or 
                receiver_input.lower() == first_name or 
                f"@{receiver_input.lower().lstrip('@')}" == f"@{username}"):
                receiver_id = uid
                break
        
        if not receiver_id:
            await update.message.reply_text("❌ لم يتم العثور على المستخدم. يرجى استخدام:\n- معرف المستخدم\n- اليوزر\n- الاسم الأول\n\nحاول مرة أخرى:")
            return TRANSFER_USER
    
    if receiver_id == user_id:
        await update.message.reply_text("❌ لا يمكن تحويل الرصيد إلى نفسك. حاول مرة أخرى:")
        return TRANSFER_USER
    
    if receiver_id not in users_data:
        await update.message.reply_text("❌ المستخدم غير موجود. حاول مرة أخرى:")
        return TRANSFER_USER
    
    if is_user_banned(receiver_id):
        await update.message.reply_text("❌ لا يمكن تحويل الرصيد إلى مستخدم محظور. حاول مرة أخرى:")
        return TRANSFER_USER
    
    amount = context.user_data.get('transfer_amount')
    if not amount:
        await update.message.reply_text("❌ حدث خطأ. الرجاء البدء من جديد.")
        return ConversationHandler.END
    
    fee_percent = bot_settings['transfer_fee_percent']
    fee = int((amount * fee_percent) / 100)
    net_amount = amount - fee
    
    sender_data = users_data[user_id]
    receiver_data = users_data[receiver_id]
    
    keyboard = [
        [
            InlineKeyboardButton("✅ تأكيد التحويل", callback_data="confirm_transfer"),
            InlineKeyboardButton("❌ إلغاء", callback_data="cancel_transfer")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    transfer_details = f"""
📋 تفاصيل التحويل:

👤 المرسل:
• الاسم: {sender_data['first_name']}
• المعرف: {user_id}
• الرصيد الحالي: {sender_data['balance']} ليرة

👤 المستلم:
• الاسم: {receiver_data['first_name']}
• المعرف: {receiver_id}
• الرصيد الحالي: {receiver_data['balance']} ليرة

💰 المبلغ: {amount} ليرة
📈 رسوم التحويل: {fee_percent}%
💸 الرسوم: {fee} ليرة
✅ المبلغ الصافي: {net_amount} ليرة

📊 بعد التحويل:
• رصيدك الجديد: {sender_data['balance'] - amount} ليرة
• رصيد المستلم الجديد: {receiver_data['balance'] + net_amount} ليرة

هل تريد تأكيد عملية التحويل؟
"""
    
    context.user_data['receiver_id'] = receiver_id
    context.user_data['transfer_fee'] = fee
    context.user_data['net_amount'] = net_amount
    
    await update.message.reply_text(transfer_details, reply_markup=reply_markup)
    
    return ConversationHandler.END

# تأكيد التحويل
async def confirm_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if not await require_syrian_verification(user_id, context, query=query):
        return
    
    amount = context.user_data.get('transfer_amount')
    receiver_id = context.user_data.get('receiver_id')
    fee = context.user_data.get('transfer_fee')
    net_amount = context.user_data.get('net_amount')
    
    if not amount or not receiver_id:
        await query.edit_message_text("❌ حدث خطأ في بيانات التحويل. يرجى المحاولة مرة أخرى.")
        context.user_data.clear()
        return
    
    success, message = transfer_balance(user_id, receiver_id, amount)
    
    if success:
        sender_data = users_data[user_id]
        receiver_data = users_data[receiver_id]
        
        confirmation_text = f"""
✅ تم التحويل بنجاح!

📋 تفاصيل العملية:
👤 من: {sender_data['first_name']} (@{sender_data.get('username', 'لا يوجد')})
👤 إلى: {receiver_data['first_name']} (@{receiver_data.get('username', 'لا يوجد')})
💰 المبلغ المحول: {amount} ليرة
📈 رسوم التحويل: {bot_settings['transfer_fee_percent']}%
💸 الرسوم: {fee} ليرة
✅ المبلغ الصافي: {net_amount} ليرة

📊 الرصيد الجديد:
• رصيدك: {sender_data['balance']} ليرة
• رصيد المستلم: {receiver_data['balance']} ليرة

📅 تاريخ العملية: {datetime.now().strftime('%Y-%m-%d %H:%M')}
🆔 رقم العملية: {len(transfer_logs)}
"""
        
        try:
            await context.bot.send_message(
                receiver_id,
                f"🎉 استلام تحويل جديد!\n\n"
                f"👤 من: {sender_data['first_name']} (@{sender_data.get('username', 'لا يوجد')})\n"
                f"💰 المبلغ: {net_amount} ليرة\n"
                f"📊 رصيدك الجديد: {receiver_data['balance']} ليرة\n"
                f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"🆔 رقم العملية: {len(transfer_logs)}"
            )
        except Exception as e:
            logger.error(f"❌ خطأ في إرسال إشعار التحويل للمستلم: {e}")
        
        await query.edit_message_text(confirmation_text)
    else:
        await query.edit_message_text(f"❌ فشل التحويل: {message}")
    
    context.user_data.clear()

# إلغاء التحويل
async def cancel_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data.clear()
    
    await query.edit_message_text("❌ تم إلغاء عملية التحويل.")
    
    keyboard = [
        [InlineKeyboardButton("💰 رصيدي", callback_data="balance"),
         InlineKeyboardButton("📈 الإحصائيات", callback_data="stats")],
        [InlineKeyboardButton("🤝 دعوة أصدقاء", callback_data="invite"),
         InlineKeyboardButton("🎁 مكافأة يومية", callback_data="daily_bonus")],
        [InlineKeyboardButton("🎁 كود الهدية", callback_data="enter_gift"),
         InlineKeyboardButton("📢 قناة الاشتراك", callback_data="channels")],
        [InlineKeyboardButton("💳 سحب رصيد", callback_data="withdraw"),
         InlineKeyboardButton("🔄 تحويل رصيد", callback_data="transfer_balance")],
        [InlineKeyboardButton("🛠 الدعم", callback_data="support")]
    ]
    
    if query.from_user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🛠 لوحة المطور", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text="🏠 تم العودة إلى القائمة الرئيسية",
        reply_markup=reply_markup
    )

# عرض لوحة المطور
async def show_admin_panel(user_id, context):
    total_users = len(users_data)
    total_referrals = sum(len(refs) for refs in user_referrals.values())
    total_balance = sum(user['balance'] for user in users_data.values())
    
    pending_withdrawals = 0
    for w in withdrawals_data.values():
        if w['status'] == 'pending':
            pending_withdrawals += 1
    
    admin_text = f"""
🛠 لوحة تحكم المطور

👥 إجمالي المستخدمين السوريين: {total_users}
📤 إجمالي الإحالات: {total_referrals}
💰 إجمالي الرصيد: {total_balance} ليـرة
⏳ طلبات السحب المعلقة: {pending_withdrawals}
⛔ عدد الممنوعين: {len(banned_users)}
🔄 عدد عمليات التحويل: {len(transfer_logs)}
📢 قناة التقارير: {REPORTS_CHANNEL}
💰 الحد الأدنى للسحب: {bot_settings['min_withdraw']} ليرة
🤝 مكافأة الإحالة: {bot_settings['referral_bonus']} ليرة
🎁 المكافأة اليومية: {bot_settings['daily_bonus_min']}-{bot_settings['daily_bonus_max']} ليرة
🔄 رسوم التحويل: {bot_settings['transfer_fee_percent']}%
📅 آخر تحديث: {datetime.now().strftime("%H:%M:%S")}

⚙️ إعدادات التشغيل:
• مكافأة الإحالة: {bot_settings['referral_bonus']} ليـرة
• الحد الأدنى للسحب: {bot_settings['min_withdraw']} ليـرة
• قناة الاشتراك: {REQUIRED_CHANNELS[0]['username']}
• قناة التقارير: {REPORTS_CHANNEL}
• نظام التخزين: مؤقت في الذاكرة
    """
    
    keyboard = [
        [InlineKeyboardButton("📊 تفاصيل الإحصائيات", callback_data="detailed_stats"),
         InlineKeyboardButton("👥 قائمة المستخدمين", callback_data="user_list")],
        [InlineKeyboardButton("💰 طلبات السحب", callback_data="withdrawal_requests"),
         InlineKeyboardButton("⛔ قائمة المحظورين", callback_data="unban_user_menu")],
        [InlineKeyboardButton("⚙️ تغيير الحد الأدنى للسحب", callback_data="change_min_withdraw"),
         InlineKeyboardButton("🎁 إضافة كود هدية", callback_data="create_gift_code")],
        [InlineKeyboardButton("🤝 تغيير مكافأة الإحالة", callback_data="change_referral_bonus"),
         InlineKeyboardButton("🎁 تغيير المكافأة اليومية", callback_data="change_daily_bonus")],
        [InlineKeyboardButton("🔄 تغيير نسبة التحويل", callback_data="change_transfer_fee"),
         InlineKeyboardButton("📢 البث للمستخدمين", callback_data="broadcast_message")],
        [InlineKeyboardButton("⛔ حظر مستخدم يدوياً", callback_data="manual_ban_user"),
         InlineKeyboardButton("📊 إحصائيات الهدايا", callback_data="gift_stats")],
        [InlineKeyboardButton("📢 تغيير قناة التقارير", callback_data="change_reports_channel"),
         InlineKeyboardButton("🔄 تحديث الإحصائيات", callback_data="refresh_stats")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user_id,
        text=admin_text,
        reply_markup=reply_markup
    )

# معالجة اختيار طريقة السحب
async def handle_withdraw_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if not await require_syrian_verification(user_id, context, query=query):
        return ConversationHandler.END
    
    method_key = query.data.replace("withdraw_", "")
    method_info = WITHDRAWAL_METHODS.get(method_key)
    
    if not method_info:
        await query.edit_message_text("❌ طريقة سحب غير صالحة.")
        return ConversationHandler.END
    
    context.user_data['withdraw_method'] = method_key
    context.user_data['withdraw_method_name'] = method_info['name']
    context.user_data['withdraw_input_prompt'] = method_info['input_prompt']
    context.user_data['withdraw_input_placeholder'] = method_info['placeholder']
    context.user_data['withdraw_input_type'] = method_info['input_type']
    
    min_withdraw = bot_settings['min_withdraw']
    
    await query.edit_message_text(
        f"💸 طريقة السحب المختارة: {method_info['name']}\n\n"
        f"💰 الرصيد المتاح: {get_balance(user_id)} ليرة\n"
        f"📊 الحد الأدنى للسحب: {min_withdraw} ليرة\n\n"
        f"🔢 الرجاء إدخال المبلغ الذي تريد سحبه:\n"
        "❌ للإلغاء، اضغط /cancel"
    )
    
    return WITHDRAW_AMOUNT

# معالجة إدخال مبلغ السحب
async def handle_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if not await require_syrian_verification(user_id, context, update=update):
        return ConversationHandler.END
    
    try:
        amount = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال رقم صحيح. حاول مرة أخرى:")
        return WITHDRAW_AMOUNT
    
    balance = get_balance(user_id)
    min_withdraw = bot_settings['min_withdraw']
    
    if amount < min_withdraw:
        await update.message.reply_text(
            f"⚠️ الحد الأدنى للسحب هو {min_withdraw} ليرة\n"
            f"💰 رصيدك الحالي: {balance} ليرة\n\n"
            f"تحتاج إلى {min_withdraw - amount} ليرة إضافية للسحب.\n\n"
            f"🔢 الرجاء إدخال مبلغ جديد:\n"
            "❌ للإلغاء، اضغط /cancel"
        )
        return WITHDRAW_AMOUNT
    
    if amount > balance:
        await update.message.reply_text(
            f"❌ المبلغ أكبر من رصيدك المتاح\n"
            f"💰 الرصيد الحالي: {balance} ليرة\n\n"
            f"🔢 الرجاء إدخال مبلغ أقل أو يساوي رصيدك:\n"
            "❌ للإلغاء، اضغط /cancel"
        )
        return WITHDRAW_AMOUNT
    
    context.user_data['withdraw_amount'] = amount
    
    method_name = context.user_data.get('withdraw_method_name')
    input_prompt = context.user_data.get('withdraw_input_prompt')
    placeholder = context.user_data.get('withdraw_input_placeholder')
    input_type = context.user_data.get('withdraw_input_type')
    
    await update.message.reply_text(
        f"💳 طريقة السحب: {method_name}\n"
        f"💰 المبلغ: {amount} ليرة\n\n"
        f"{input_prompt}\n"
        f"📝 {placeholder}\n"
        "❌ للإلغاء، اضغط /cancel"
    )
    
    return WITHDRAW_DETAILS

# معالجة إدخال تفاصيل الاستلام
async def handle_withdraw_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if not await require_syrian_verification(user_id, context, update=update):
        return ConversationHandler.END
    
    receiver_info = update.message.text.strip()
    
    input_type = context.user_data.get('withdraw_input_type')
    
    if input_type == 'syrian_phone':
        is_valid, clean_phone = verify_syrian_phone(receiver_info)
        
        if not is_valid:
            await update.message.reply_text(
                f"❌ الرقم الذي أدخلته ليس سوريًا!\n\n"
                f"📱 يجب أن يكون رقم هاتف سوري:\n"
                f"• يبدأ بـ 09\n"
                f"• يتكون من 10 أرقام\n"
                f"• مثال: 0991234567\n\n"
                f"الرجاء إدخال رقم سوري صحيح:"
            )
            return WITHDRAW_DETAILS
        
        receiver_info = clean_phone
    
    if not receiver_info or len(receiver_info) < 3:
        await update.message.reply_text("❌ الرجاء إدخال معلومات صحيحة. حاول مرة أخرى:")
        return WITHDRAW_DETAILS
    
    context.user_data['receiver_info'] = receiver_info
    
    amount = context.user_data.get('withdraw_amount')
    method_key = context.user_data.get('withdraw_method')
    method_name = context.user_data.get('withdraw_method_name')
    
    keyboard = [
        [
            InlineKeyboardButton("✅ تأكيد السحب", callback_data="confirm_withdraw"),
            InlineKeyboardButton("❌ إلغاء", callback_data="cancel_withdraw")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if input_type == 'syrian_phone':
        details_text = f"📱 رقم الهاتف السوري: {receiver_info}"
    elif input_type == 'address':
        details_text = f"📍 عنوان الاستلام: {receiver_info}"
    elif input_type == 'account':
        details_text = f"🏦 رقم الحساب/العنوان: {receiver_info}"
    else:
        details_text = f"📋 تفاصيل الاستلام: {receiver_info}"
    
    await update.message.reply_text(
        f"📋 تفاصيل طلب السحب:\n\n"
        f"✅ أنت مستخدم سوري موثق\n"
        f"📞 رقمك المسجل: {users_data[user_id]['syrian_phone']}\n"
        f"💰 المبلغ: {amount} ليرة\n"
        f"💳 طريقة السحب: {method_name}\n"
        f"👤 المستخدم: {user.first_name}\n"
        f"📱 اليوزر: @{user.username if user.username else 'لا يوجد'}\n"
        f"{details_text}\n\n"
        f"هل تريد تأكيد طلب السحب؟",
        reply_markup=reply_markup
    )
    
    return ConversationHandler.END

# تأكيد طلب السحب
async def confirm_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if not await require_syrian_verification(user_id, context, query=query):
        return
    
    amount = context.user_data.get('withdraw_amount')
    method_key = context.user_data.get('withdraw_method')
    method_name = context.user_data.get('withdraw_method_name')
    receiver_info = context.user_data.get('receiver_info')
    input_type = context.user_data.get('withdraw_input_type')
    
    if not amount or not method_key or not receiver_info:
        await query.edit_message_text("❌ حدث خطأ في بيانات السحب. يرجى المحاولة مرة أخرى.")
        context.user_data.clear()
        return
    
    update_balance(user_id, -amount)
    
    global withdrawal_counter
    withdrawal_id = withdrawal_counter + 1
    withdrawal_counter += 1
    
    withdrawals_data[withdrawal_id] = {
        'user_id': user_id,
        'amount': amount,
        'method': method_key,
        'receiver_info': receiver_info,
        'status': 'pending',
        'created_at': datetime.now()
    }
    
    user = query.from_user
    
    if input_type == 'syrian_phone':
        details_text = f"📱 رقم الهاتف: {receiver_info}"
    elif input_type == 'address':
        details_text = f"📍 عنوان الاستلام: {receiver_info}"
    elif input_type == 'account':
        details_text = f"🏦 رقم الحساب/العنوان: {receiver_info}"
    else:
        details_text = f"📋 تفاصيل الاستلام: {receiver_info}"
    
    # إرسال تقرير السحب
    try:
        user_data = users_data[user_id]
        withdrawal_data = {
            'user_id': user_id,
            'amount': amount,
            'method': method_key,
            'receiver_info': receiver_info,
            'id': withdrawal_id
        }
        await send_withdrawal_report(context, withdrawal_data, user_data)
    except Exception as e:
        logger.error(f"خطأ في إرسال تقرير السحب: {e}")
    
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"🆘 طلب سحب جديد\n\n"
            f"👤 المستخدم: {user.first_name}\n"
            f"📱 اليوزر: @{user.username if user.username else 'لا يوجد'}\n"
            f"🆔 المعرف: {user.id}\n"
            f"📞 الرقم المسجل: {users_data[user_id]['syrian_phone']}\n"
            f"💰 المبلغ: {amount} ليرة\n"
            f"💳 طريقة السحب: {method_name}\n"
            f"{details_text}\n"
            f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"⚡ الرصيد المتبقي للمستخدم: {get_balance(user_id)} ليرة\n"
            f"🆔 رقم الطلب: {withdrawal_id}"
        )
    except Exception as e:
        logger.error(f"خطأ في إرسال إشعار السحب للمطور: {e}")
    
    confirmation_text = f"""
✅ تم تأكيد طلب السحب بنجاح!

📋 تفاصيل الطلب:
💰 المبلغ: {amount} ليرة
💳 طريقة السحب: {method_name}
"""
    
    if input_type == 'syrian_phone':
        confirmation_text += f"📱 رقم الهاتف: {receiver_info}\n"
    elif input_type == 'address':
        confirmation_text += f"📍 عنوان الاستلام: {receiver_info}\n"
    elif input_type == 'account':
        confirmation_text += f"🏦 رقم الحساب/العنوان: {receiver_info}\n"
    
    confirmation_text += f"""
📅 تاريخ الطلب: {datetime.now().strftime('%Y-%m-%d %H:%M')}
🆔 رقم الطلب: {withdrawal_id}
⏳ حالة الطلب: قيد المراجعة

📞 سيتواصل معك الدعم خلال 24 ساعة.
💰 رصيدك الحالي: {get_balance(user_id)} ليرة
"""
    
    await query.edit_message_text(confirmation_text)
    
    context.user_data.clear()

# إلغاء طلب السحب
async def cancel_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data.clear()
    
    await query.edit_message_text("❌ تم إلغاء طلب السحب.")
    
    keyboard = [
        [InlineKeyboardButton("💰 رصيدي", callback_data="balance"),
         InlineKeyboardButton("📈 الإحصائيات", callback_data="stats")],
        [InlineKeyboardButton("🤝 دعوة أصدقاء", callback_data="invite"),
         InlineKeyboardButton("🎁 مكافأة يومية", callback_data="daily_bonus")],
        [InlineKeyboardButton("🎁 كود الهدية", callback_data="enter_gift"),
         InlineKeyboardButton("📢 قناة الاشتراك", callback_data="channels")],
        [InlineKeyboardButton("💳 سحب رصيد", callback_data="withdraw"),
         InlineKeyboardButton("🔄 تحويل رصيد", callback_data="transfer_balance")],
        [InlineKeyboardButton("🛠 الدعم", callback_data="support")]
    ]
    
    if query.from_user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🛠 لوحة المطور", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=query.from_user.id,
        text="🏠 تم العودة إلى القائمة الرئيسية",
        reply_markup=reply_markup
    )

# أمر معالجة طلب السحب
async def process_withdrawal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ ليس لديك صلاحية للوصول إلى هذا الأمر.")
        return
    
    message_text = update.message.text
    try:
        parts = message_text.split('_')
        if len(parts) < 2:
            await update.message.reply_text("❌ صيغة الأمر غير صحيحة.\nمثال: /process_1")
            return
        
        withdrawal_id = int(parts[1])
    except (IndexError, ValueError):
        await update.message.reply_text("❌ رقم غير صالح. يرجى إدخال رقم صحيح.\nمثال: /process_1")
        return
    
    if withdrawal_id not in withdrawals_data:
        await update.message.reply_text(f"❌ طلب السحب رقم {withdrawal_id} غير موجود.")
        return
    
    withdrawal = withdrawals_data[withdrawal_id]
    
    if withdrawal['status'] != 'pending':
        await update.message.reply_text(f"❌ طلب السحب رقم {withdrawal_id} تمت معالجته مسبقاً.")
        return
    
    user_id_withdraw = withdrawal['user_id']
    amount = withdrawal['amount']
    method = withdrawal['method']
    receiver_info = withdrawal['receiver_info']
    
    method_info = WITHDRAWAL_METHODS.get(method, {"name": "غير معروف"})
    method_name = method_info['name']
    
    withdrawal['status'] = 'completed'
    withdrawal['process_date'] = datetime.now()
    
    first_name = "مستخدم"
    username = "لا يوجد"
    
    if user_id_withdraw in users_data:
        user_data = users_data[user_id_withdraw]
        first_name = user_data.get('first_name', 'مستخدم')
        username = user_data.get('username', 'لا يوجد')
    
    # إرسال تقرير معالجة السحب
    try:
        await send_withdrawal_processed_report(context, withdrawal_id, user_id)
    except Exception as e:
        logger.error(f"خطأ في إرسال تقرير معالجة السحب: {e}")
    
    try:
        confirmation_message = f"""
🎉 تم استلام المبلغ بنجاح!

✅ تأكيد الاستلام:
💰 المبلغ: {amount} ليرة
💳 طريقة السحب: {method_name}
📅 تاريخ التحويل: {datetime.now().strftime('%Y-%m-%d %H:%M')}
🆔 رقم العملية: {withdrawal_id}

📋 تم تحويل المبلغ إلى:
"""
        if method == "syriatel_cash":
            confirmation_message += f"📱 رقم الهاتف: {receiver_info}"
        elif method in ["sham_cash_syr", "sham_cash_usd"]:
            confirmation_message += f"📍 العنوان: {receiver_info}"
        elif method == "paynes":
            confirmation_message += f"🏦 الحساب/العنوان: {receiver_info}"
        else:
            confirmation_message += f"📋 تفاصيل الاستلام: {receiver_info}"
        
        confirmation_message += "\n\n💰 يمكنك الآن استخدام المبلغ بأي طريقة تريد."
        confirmation_message += "\n\n📞 للاستفسار: https://t.me/Sports_5K"
        
        await context.bot.send_message(
            chat_id=user_id_withdraw,
            text=confirmation_message
        )
        
        await context.bot.send_message(
            chat_id=user_id_withdraw,
            text="🎊 تم إرسال المبلغ بنجاح! شكراً لاستخدامك خدمتنا."
        )
        
        await update.message.reply_text(
            f"✅ تمت معالجة طلب السحب رقم {withdrawal_id} بنجاح!\n\n"
            f"👤 المستخدم: {first_name} (@{username})\n"
            f"💰 المبلغ: {amount} ليرة\n"
            f"💳 طريقة السحب: {method_name}\n\n"
            f"📬 تم إرسال تأكيد الاستلام للمستخدم."
        )
        
    except Exception as e:
        logger.error(f"خطأ في إرسال تأكيد الاستلام للمستخدم: {e}")
        await update.message.reply_text(
            f"⚠️ تمت معالجة الطلب لكن حدث خطأ في إرسال تأكيد الاستلام للمستخدم: {e}\n\n"
            f"👤 المستخدم: {first_name} (@{username})\n"
            f"💰 المبلغ: {amount} ليرة\n"
            f"💳 طريقة السحب: {method_name}"
        )

# تغيير الحد الأدنى للسحب
async def change_min_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    if user_id != ADMIN_ID:
        await query.edit_message_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    current_min = bot_settings['min_withdraw']
    
    await query.edit_message_text(
        f"💰 الحد الأدنى الحالي للسحب: {current_min} ليرة\n\n"
        f"🔢 الرجاء إدخال الحد الأدنى الجديد للسحب (بالليرة):\n"
        "❌ للإلغاء، اضغط /cancel"
    )
    
    return CHANGE_MIN_WITHDRAW

# معالجة إدخال الحد الأدنى الجديد للسحب
async def handle_new_min_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ ليس لديك صلاحية للوصول إلى هذه الميزة.")
        return ConversationHandler.END
    
    try:
        new_min = int(update.message.text.strip())
        
        if new_min <= 0:
            await update.message.reply_text("❌ الرقم يجب أن يكون أكبر من صفر. حاول مرة أخرى:")
            return CHANGE_MIN_WITHDRAW
        
        bot_settings['min_withdraw'] = new_min
        
        await update.message.reply_text(f"✅ تم تحديث الحد الأدنى للسحب إلى {new_min} ليرة")
        
        await show_admin_panel(user_id, context)
        
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال رقم صحيح. حاول مرة أخرى:")
        return CHANGE_MIN_WITHDRAW

# إلغاء المحادثة
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"تم إلغاء العملية.\n"
        f"يمكنك البدء مجدداً باستخدام /start",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

# أمر المطور /admin
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ ليس لديك صلاحية للوصول إلى هذا الأمر.")
        return
    
    await show_admin_panel(user_id, context)

# معالجة أوامر process_
async def handle_process_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_withdrawal_command(update, context)

# أمر إعادة التشغيل /reboot
async def reboot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ ليس لديك صلاحية للوصول إلى هذا الأمر.")
        return
    
    await update.message.reply_text("🔄 جاري إعادة تشغيل النظام...")
    
    users_data.clear()
    withdrawals_data.clear()
    gift_codes.clear()
    used_gift_codes.clear()
    user_referrals.clear()
    banned_users.clear()
    transfer_logs.clear()
    global withdrawal_counter
    withdrawal_counter = 0
    
    await update.message.reply_text("✅ تم إعادة تشغيل النظام بنجاح!")

# أمر البث /broadcast
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ ليس لديك صلاحية للوصول إلى هذا الأمر.")
        return
    
    if not context.args:
        await update.message.reply_text("❌ يرجى كتابة الرسالة بعد الأمر.\nمثال: /broadcast مرحباً بالجميع!")
        return
    
    message = " ".join(context.args)
    
    await update.message.reply_text(f"📤 جاري إرسال الرسالة إلى {len(users_data)} مستخدم...")
    
    success = 0
    failed = 0
    
    for user_id in users_data.keys():
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 إشعار من الإدارة:\n\n{message}")
            success += 1
        except:
            failed += 1
    
    await update.message.reply_text(f"✅ تم إرسال الرسالة:\n✅ نجح: {success}\n❌ فشل: {failed}")

# معالج الأخطاء
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"حدث خطأ: {context.error}")
    
    try:
        await update.message.reply_text("❌ حدث خطأ في النظام. يرجى المحاولة مرة أخرى باستخدام /start")
    except:
        pass

# الدالة الرئيسية
def main():
    application = ApplicationBuilder().token(TOKEN).build()
    
    conv_handler_start = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHECK_SUB_BEFORE_MATH: [
                CallbackQueryHandler(check_sub_math_callback, pattern="^check_sub_math$"),
            ],
            VERIFY_SYRIAN_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_during_verification),
                MessageHandler(filters.CONTACT, handle_contact)
            ],
            VERIFY_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_code_handler)],
            VERIFY_MATH: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_math)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )
    
    conv_handler_withdraw = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_withdraw_method, pattern="^withdraw_.*$")],
        states={
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_amount)],
            WITHDRAW_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_details)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(cancel_withdraw, pattern="^cancel_withdraw$")],
    )
    
    conv_handler_transfer = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^transfer_balance$")],
        states={
            TRANSFER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_transfer_amount)],
            TRANSFER_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_transfer_user)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(cancel_transfer, pattern="^cancel_transfer$")],
    )
    
    conv_handler_min_withdraw = ConversationHandler(
        entry_points=[CallbackQueryHandler(change_min_withdraw, pattern="^change_min_withdraw$")],
        states={
            CHANGE_MIN_WITHDRAW: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_min_withdraw)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    conv_handler_enter_gift = ConversationHandler(
        entry_points=[CallbackQueryHandler(enter_gift_code, pattern="^enter_gift$")],
        states={
            ENTER_GIFT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_gift_code)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    conv_handler_create_gift = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_gift_code, pattern="^create_gift_code$")],
        states={
            CREATE_GIFT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_create_gift_code)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    conv_handler_referral_bonus = ConversationHandler(
        entry_points=[CallbackQueryHandler(change_referral_bonus, pattern="^change_referral_bonus$")],
        states={
            CHANGE_REFERRAL_BONUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_change_referral_bonus)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    conv_handler_daily_bonus = ConversationHandler(
        entry_points=[CallbackQueryHandler(change_daily_bonus, pattern="^change_daily_bonus$")],
        states={
            CHANGE_DAILY_BONUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_change_daily_bonus)],
            CHANGE_DAILY_BONUS + 1: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_change_daily_bonus_max)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    conv_handler_transfer_fee = ConversationHandler(
        entry_points=[CallbackQueryHandler(change_transfer_fee, pattern="^change_transfer_fee$")],
        states={
            CHANGE_TRANSFER_FEE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_change_transfer_fee)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    conv_handler_broadcast = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_message, pattern="^broadcast_message$")],
        states={
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast_message)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    conv_handler_manual_ban = ConversationHandler(
        entry_points=[CallbackQueryHandler(manual_ban_user_prompt, pattern="^manual_ban_user$")],
        states={
            MANUAL_BAN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manual_ban_user)],
            MANUAL_BAN_USER + 1: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manual_ban_reason)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    conv_handler_unban = ConversationHandler(
        entry_points=[CallbackQueryHandler(unban_user_prompt, pattern="^unban_user_menu$")],
        states={
            UNBAN_USER: [CallbackQueryHandler(button_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    conv_handler_reports_channel = ConversationHandler(
        entry_points=[CallbackQueryHandler(change_reports_channel, pattern="^change_reports_channel$")],
        states={
            CHANGE_REPORTS_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_change_reports_channel)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    application.add_handler(conv_handler_start)
    application.add_handler(conv_handler_withdraw)
    application.add_handler(conv_handler_transfer)
    application.add_handler(conv_handler_min_withdraw)
    application.add_handler(conv_handler_enter_gift)
    application.add_handler(conv_handler_create_gift)
    application.add_handler(conv_handler_referral_bonus)
    application.add_handler(conv_handler_daily_bonus)
    application.add_handler(conv_handler_transfer_fee)
    application.add_handler(conv_handler_broadcast)
    application.add_handler(conv_handler_manual_ban)
    application.add_handler(conv_handler_unban)
    application.add_handler(conv_handler_reports_channel)
    
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("reboot", reboot_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    application.add_handler(MessageHandler(filters.Regex(r'^/process_\d+$'), handle_process_command))
    application.add_handler(MessageHandler(filters.Regex(r'^/unban_\d+$'), lambda update, context: button_handler(update, context)))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    
    application.add_error_handler(error_handler)
    
    logger.info("✅ جاري تشغيل البوت...")
    logger.info(f"📢 قناة التقارير: {REPORTS_CHANNEL}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()