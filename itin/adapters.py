from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from allauth.socialaccount.models import SocialAccount
from django.contrib import messages
import sys

User = get_user_model()


class CustomAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        """
        Zakáže klasickou registraci - pouze přes Entra!
        """
        return False


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def _get_email_from_sociallogin(self, sociallogin):
        """
        Helper metoda pro získání emailu z různých zdrojů.
        Email NEMUSÍ být unikátní - použijeme preferred_username.
        """
        extra_data = sociallogin.account.extra_data
        
        # 1. Zkusíme email_addresses
        if sociallogin.email_addresses:
            return sociallogin.email_addresses[0].email
        
        # 2. Zkusíme extra_data - různé zdroje
        if 'userinfo' in extra_data and 'email' in extra_data['userinfo']:
            return extra_data['userinfo']['email']
        
        if 'id_token' in extra_data and 'email' in extra_data['id_token']:
            return extra_data['id_token']['email']
        
        if 'email' in extra_data:
            return extra_data['email']
        
        # 3. Použij preferred_username jako email (může být username bez @)
        preferred_username = None
        if 'id_token' in extra_data and 'preferred_username' in extra_data['id_token']:
            preferred_username = extra_data['id_token']['preferred_username']
        elif 'preferred_username' in extra_data:
            preferred_username = extra_data['preferred_username']
        
        return preferred_username

    def _get_username_from_sociallogin(self, sociallogin):
        """
        Helper pro získání username - CELÝ preferred_username (unikátní identifikátor).
        """
        extra_data = sociallogin.account.extra_data
        
        if 'id_token' in extra_data and 'preferred_username' in extra_data['id_token']:
            return extra_data['id_token']['preferred_username']
        elif 'preferred_username' in extra_data:
            return extra_data['preferred_username']
        
        # Fallback na email
        return self._get_email_from_sociallogin(sociallogin)

    def pre_social_login(self, request, sociallogin):
        """
        Invoked just after a user successfully authenticates via a social provider.
        Propojujeme podle USERNAME (preferred_username), ne podle emailu!
        """
        print(f"=== PRE_SOCIAL_LOGIN ===", file=sys.stderr)
        print(f"is_existing: {sociallogin.is_existing}", file=sys.stderr)
        
        if sociallogin.is_existing:
            print(f"User already exists, returning", file=sys.stderr)
            return

        uid = sociallogin.account.uid
        provider = sociallogin.account.provider
        
        print(f"UID: {uid}, Provider: {provider}", file=sys.stderr)
        
        # Zkontrolujeme podle UID
        try:
            social_account = SocialAccount.objects.get(provider=provider, uid=uid)
            print(f"Found existing social account, connecting", file=sys.stderr)
            sociallogin.connect(request, social_account.user)
            return
        except SocialAccount.DoesNotExist:
            print(f"No existing social account found", file=sys.stderr)
            pass

        # Zkusíme najít podle USERNAME (preferred_username)
        username = self._get_username_from_sociallogin(sociallogin)
        print(f"Username from preferred_username: {username}", file=sys.stderr)
        
        if not username:
            print(f"No username found, returning", file=sys.stderr)
            return

        try:
            user = User.objects.get(username=username)
            print(f"Found user by username, connecting", file=sys.stderr)
            sociallogin.connect(request, user)
            
            messages.success(
                request,
                f"Váš existující účet ({username}) byl úspěšně propojen s UJF Identity (Entra ID). "
                f"Příště se můžete přihlásit jen přes UJF Identity."
            )
            request.session['_social_account_connected'] = True
        except User.DoesNotExist:
            print(f"User does not exist, will auto-signup", file=sys.stderr)
            pass

    def save_user(self, request, sociallogin, form=None):
        """
        Volá se při vytvoření nového uživatele přes social login.
        """
        print(f"=== SAVE_USER ===", file=sys.stderr)
        user = super().save_user(request, sociallogin, form)
        print(f"User saved: username={user.username}, email={user.email}", file=sys.stderr)
        
        if not request.session.get('_social_account_connected'):
            name = f"{user.first_name} {user.last_name}".strip() or user.username
            
            messages.success(
                request,
                f"Vítejte! Váš nový účet byl vytvořen s následujícími údaji:\n"
                f"• Jméno: {name}\n"
                f"• Username: {user.username}\n"
                f"• Propojeno s: UJF Identity (Entra ID)"
            )
        else:
            request.session.pop('_social_account_connected', None)
        
        return user

    def populate_user(self, request, sociallogin, data):
        """
        Naplní data nového uživatele z informací ze social providera.
        """
        print(f"=== POPULATE_USER ===", file=sys.stderr)
        print(f"Data: {data}", file=sys.stderr)
        print(f"Extra data: {sociallogin.account.extra_data}", file=sys.stderr)
        
        user = super().populate_user(request, sociallogin, data)
        extra_data = sociallogin.account.extra_data
        
        # Username - CELÝ preferred_username (unikátní)
        if not user.username:
            user.username = self._get_username_from_sociallogin(sociallogin)
            print(f"Set username: {user.username}", file=sys.stderr)
        
        # Email - může být neúplný nebo duplikát
        if not user.email:
            user.email = self._get_email_from_sociallogin(sociallogin)
            print(f"Set email: {user.email}", file=sys.stderr)
        
        # Jméno a příjmení - zkusíme userinfo i id_token
        if not user.first_name:
            if 'userinfo' in extra_data and 'given_name' in extra_data['userinfo']:
                user.first_name = extra_data['userinfo']['given_name']
            elif 'id_token' in extra_data and 'given_name' in extra_data['id_token']:
                user.first_name = extra_data['id_token']['given_name']
            elif 'given_name' in extra_data:
                user.first_name = extra_data['given_name']
        
        if not user.last_name:
            if 'userinfo' in extra_data and 'family_name' in extra_data['userinfo']:
                user.last_name = extra_data['userinfo']['family_name']
            elif 'id_token' in extra_data and 'family_name' in extra_data['id_token']:
                user.last_name = extra_data['id_token']['family_name']
            elif 'family_name' in extra_data:
                user.last_name = extra_data['family_name']
        
        # Fallback: celé jméno
        if not user.first_name and not user.last_name:
            name = None
            if 'userinfo' in extra_data and 'name' in extra_data['userinfo']:
                name = extra_data['userinfo']['name']
            elif 'id_token' in extra_data and 'name' in extra_data['id_token']:
                name = extra_data['id_token']['name']
            elif 'name' in extra_data:
                name = extra_data['name']
            
            if name:
                name_parts = name.split(' ', 1)
                user.first_name = name_parts[0]
                if len(name_parts) > 1:
                    user.last_name = name_parts[1]
        
        print(f"Populated user: username={user.username}, email={user.email}, name={user.first_name} {user.last_name}", file=sys.stderr)
        return user

    def is_auto_signup_allowed(self, request, sociallogin):
        """
        Automatický signup bez ptaní - VŽDY True.
        """
        print(f"=== IS_AUTO_SIGNUP_ALLOWED ===", file=sys.stderr)
        
        # Ujistíme se, že máme email pro allauth
        if not sociallogin.email_addresses:
            email = self._get_email_from_sociallogin(sociallogin)
            if email:
                from allauth.account.models import EmailAddress as EmailAddressModel
                email_obj = EmailAddressModel(email=email, verified=True, primary=True)
                sociallogin.email_addresses = [email_obj]
                print(f"Added email to sociallogin: {email}", file=sys.stderr)
        
        print(f"Returning: True", file=sys.stderr)
        return True
    
    def is_open_for_signup(self, request, sociallogin):
        """
        Signup přes Entra je vždy povolený.
        """
        print(f"=== IS_OPEN_FOR_SIGNUP (social) ===", file=sys.stderr)
        return True
