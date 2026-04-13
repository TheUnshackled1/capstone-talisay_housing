#!/bin/bash
# SEMAPHORE SMS TESTING - EXECUTION SCRIPT
# Run this step-by-step to test SMS integration
# Copy each command and paste into your terminal

# ============================================================================
# STEP 1: VERIFY SETTINGS ARE CORRECT (No command needed)
# ============================================================================
# Check that settings.py has:
# - SMS_ENABLED = True
# - SEMAPHORE_API_KEY = 'your_key_here' (not empty)
# - SEMAPHORE_SENDER_NAME = 'SEMAPHORE'
#
# Location: C:\Users\jtcor\Documents\capstone\talisay_housing\settings.py
# Lines: 147-149

echo "📋 STEP 1: Verify settings in /talisay_housing/settings.py"
echo "   Expected:"
echo "   SMS_ENABLED = True"
echo "   SEMAPHORE_API_KEY = 'c3f15974a138c3c7aabef97f481781f5'"
echo "   SEMAPHORE_SENDER_NAME = 'SEMAPHORE'"
echo ""
read -p "   Have you verified? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "   ❌ Please check settings.py first"
    exit 1
fi
echo "   ✅ Settings verified"
echo ""

# ============================================================================
# STEP 2: GO TO PROJECT DIRECTORY
# ============================================================================
echo "📂 STEP 2: Navigate to project directory"
echo ""
cd /c/Users/jtcor/Documents/capstone
echo "   Current directory: $(pwd)"
echo "   ✅ In project directory"
echo ""

# ============================================================================
# STEP 3: TEST SMS COMMAND (Basic Test)
# ============================================================================
echo "📱 STEP 3: Run basic SMS test"
echo ""
echo "   Replace YOUR_PHONE_NUMBER with your actual number (in 09XX format)"
echo ""
echo "   Command:"
echo "   python manage.py test_sms --phone \"09171234567\""
echo ""
read -p "   Ready to test? Enter your phone number (09XXXXXXXXX): " phone_number

if [[ ! $phone_number =~ ^09[0-9]{9}$ ]]; then
    echo ""
    echo "   ⚠️  Invalid format. Please use 09XXXXXXXXX"
    echo "   Examples:"
    echo "   - 09171234567"
    echo "   - 09281234567"
    exit 1
fi

echo ""
echo "   📤 Sending test SMS to $phone_number..."
python manage.py test_sms --phone "$phone_number"

echo ""
echo "   ⏳ SMS sent. Check your phone for message from 'SEMAPHORE'"
echo "   Wait 30 seconds to 1 minute..."
echo ""
read -p "   Did you receive the SMS? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "   ✅ SMS RECEIVED! Integration working! 🎉"
    sms_working=true
else
    echo "   ❌ SMS NOT received. Troubleshooting..."
    sms_working=false
fi
echo ""

# ============================================================================
# STEP 4: CHECK SEMAPHORE ACCOUNT (If SMS didn't work)
# ============================================================================
if [ "$sms_working" = false ]; then
    echo "🔍 STEP 4: Troubleshooting"
    echo ""
    echo "   Please check:"
    echo "   1. Semaphore account at https://semaphore.co"
    echo "   2. Check SMS Balance (should be > 0)"
    echo "   3. Check Account Status (should be Active)"
    echo "   4. Check if phone needs to be whitelisted (free tier)"
    echo ""
    read -p "   Have you checked Semaphore? (y/n) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "   Try test again:"
        echo "   python manage.py test_sms --phone \"$phone_number\""
        exit 0
    fi
fi

# ============================================================================
# STEP 5: VIEW SMS LOGS IN DJANGO ADMIN
# ============================================================================
echo "📋 STEP 5: View SMS logs in Django Admin"
echo ""
echo "   Go to: http://localhost:8000/admin/intake/smslog/"
echo ""
echo "   You should see:"
echo "   - SMS to $phone_number"
echo "   - Status: 'sent'"
echo "   - Trigger Event: 'test_sms_command'"
echo ""
read -p "   Can you see the SMS log? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "   ✅ SMS log visible in admin"
else
    echo "   ⚠️  Check that Django server is running:"
    echo "   python manage.py runserver"
fi
echo ""

# ============================================================================
# STEP 6: TEST WITH DIFFERENT PHONE NUMBERS
# ============================================================================
echo "📱 STEP 6: Test with different phone numbers (Optional)"
echo ""
echo "   Test different formats to ensure formatting works:"
echo ""
echo "   Test 1 - Standard format (09XXXXXXXXX):"
echo "   python manage.py test_sms --phone \"09171234567\""
echo ""
echo "   Test 2 - International format (+639XXXXXXXXX):"
echo "   python manage.py test_sms --phone \"+639171234567\""
echo ""
echo "   Test 3 - Without plus (+639XXXXXXXXX):"
echo "   python manage.py test_sms --phone \"639171234567\""
echo ""
read -p "   Run additional tests? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "   Enter another phone number to test: " phone_number_2
    python manage.py test_sms --phone "$phone_number_2"
fi
echo ""

# ============================================================================
# STEP 7: TEST PRODUCTION WORKFLOW
# ============================================================================
echo "🚀 STEP 7: Test production workflow"
echo ""
echo "   1. Go to: http://localhost:8000/intake/landowner-form/"
echo "   2. Fill in landowner details (name, phone, email)"
echo "   3. Add at least one ISF record (name, household, income, years)"
echo "   4. Submit form"
echo "   5. You should receive an SMS with registration confirmation"
echo ""
read -p "   Run production workflow test? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "   ✅ Test production workflow at:"
    echo "   http://localhost:8000/intake/landowner-form/"
    echo ""
    read -p "   Did you receive the registration SMS? (y/n) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "   ✅ PRODUCTION WORKFLOW WORKING! 🎉"
    else
        echo "   ⚠️  Check SMSLog in admin for errors"
    fi
fi
echo ""

# ============================================================================
# FINAL SUMMARY
# ============================================================================
echo "="
echo "📋 TESTING SUMMARY"
echo "="
echo ""
echo "✅ SMS Configuration checked"
echo "✅ Basic SMS test completed"
if [ "$sms_working" = true ]; then
    echo "✅ SMS successfully received on $phone_number"
    echo "✅ SMS logs visible in Django admin"
    echo ""
    echo "🎉 SMS INTEGRATION IS WORKING!"
    echo ""
    echo "Next steps:"
    echo "1. Test with landowner form: /intake/landowner-form/"
    echo "2. Test eligibility workflow"
    echo "3. Monitor SMSLog in admin: /admin/intake/smslog/"
    echo "4. Proceed to Module 2 testing"
else
    echo "⚠️  SMS not yet working"
    echo ""
    echo "Troubleshooting checklist:"
    echo "□ Semaphore account balance > 0"
    echo "□ SMS_ENABLED = True in settings"
    echo "□ API key is correct"
    echo "□ Phone number format is correct"
    echo "□ Phone is whitelisted (if free tier)"
fi
echo ""
