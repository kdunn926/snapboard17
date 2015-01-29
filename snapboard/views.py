import logging
import datetime

import json

from django import forms
from django.conf import settings
from django.contrib.auth import decorators, authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.db import connection
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpResponseServerError
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.views.generic import TemplateView
from django.utils.translation import ugettext as _

try:
    from notification import models as notification
except ImportError:
    notification = None

from snapboard.forms import *
from snapboard.models import *
from snapboard.rpc import *

_log = logging.getLogger('snapboard.views')

DEFAULT_USER_SETTINGS  = UserSettings()

# USE_SNAPBOARD_LOGIN_FORM, USE_SNAPBOARD_SIGNIN should probably be removed
USE_SNAPBOARD_SIGNIN = getattr(settings, 'USE_SNAPBOARD_SIGNIN', False)
USE_SNAPBOARD_LOGIN_FORM = getattr(settings, 'USE_SNAPBOARD_LOGIN_FORM', False)
OUR_APP_NAME = getattr(settings, 'OUR_APP_NAME', None)

RPC_OBJECT_MAP = {
        "thread": Thread,
        "post": Post,
        }

RPC_ACTION_MAP = {
        "censor": rpc_censor,
        "gsticky": rpc_gsticky,
        "csticky": rpc_csticky,
        "close": rpc_close,
        "abuse": rpc_abuse,
        "watch": rpc_watch,
        "quote": rpc_quote,
        }

def snapboard_default_context(request):
    """
    Provides some default information for all templates.

    This should be added to the settings variable TEMPLATE_CONTEXT_PROCESSORS
    """
    return {
            'SNAP_MEDIA_PREFIX': SNAP_MEDIA_PREFIX,
            'SNAP_POST_FILTER': SNAP_POST_FILTER,
            'LOGIN_URL': settings.LOGIN_URL,
            'LOGOUT_URL': settings.LOGOUT_URL,
            'APP_NAME': OUR_APP_NAME,
            }


def user_settings_context(request):
    return {'user_settings': get_user_settings(request.user)}

if USE_SNAPBOARD_LOGIN_FORM:
    from snapboard.forms import LoginForm
    def login_context(request):
        '''
        All content pages that have additional content for authenticated users but
        that are also publicly viewable should have a login form in the side panel.
        '''
        response_dict = {}
        if not request.user.is_authenticated():
            response_dict.update({
                    'login_form': LoginForm(),
                    })

        return response_dict
    extra_processors = [user_settings_context, login_context]
else:
    extra_processors = [user_settings_context]

def rpc(request):
    '''
    Delegates simple rpc requests.
    '''
    if not request.POST or not request.user.is_authenticated():
        return HttpResponseServerError()

    response_dict = {}

    try:
        action = request.POST['action'].lower()
        rpc_func = RPC_ACTION_MAP[action]
    except KeyError:
        raise HttpResponseServerError()

    if action == 'quote':
        try:
            return HttpResponse(json.dumps(rpc_func(request, oid=int(request.POST['oid']))))
        except (KeyError, ValueError):
            return HttpResponseServerError()

    try:
        # oclass_str will be used as a keyword in a function call, so it must
        # be a string, not a unicode object (changed since Django went
        # unicode). Thanks to Peter Sheats for catching this.
        oclass_str =  str(request.POST['oclass'].lower())
        oclass = RPC_OBJECT_MAP[oclass_str]
    except KeyError:
        return HttpResponseServerError()

    try:
        oid = int(request.POST['oid'])

        forum_object = oclass.objects.get(pk=oid)

        response_dict.update(rpc_func(request, **{oclass_str:forum_object}))
        return HttpResponse(json.dumps(response_dict), mimetype='application/javascript')

    except oclass.DoesNotExist:
        return HttpResponseServerError()
    except KeyError:
        return HttpResponseServerError()

def thread(request, thread_id):
    try:
        thr = Thread.view_manager.get(pk=thread_id)
    except Thread.DoesNotExist:
        raise Http404

    if not thr.category.can_read(request.user):
        raise PermissionError

    render_dict = {}

    if request.user.is_authenticated():
        render_dict.update({"watched": WatchList.objects.filter(user=request.user, thread=thr).count() != 0})

    if request.POST:
        if not thr.category.can_post(request.user):
            raise PermissionError
        postform = PostForm(request.POST)
        if postform.is_valid():
            postobj = Post(thread = thr,
                    user = request.user,
                    text = postform.cleaned_data['post'],
                    )
            postobj.save() # this needs to happen before many-to-many private is assigned

            """
            if len(postform.cleaned_data['private']) > 0:
                _log.debug('thread(): new post private = %s' % postform.cleaned_data['private'])
                postobj.private = postform.cleaned_data['private']
                postobj.is_private = True
                postobj.save()
            """;
            postobj.notify()
            return HttpResponseRedirect(reverse('snapboard_locate_post', args=(postobj.id,)))
    else:
        postform = PostForm()

    # this must come after the post so new messages show up
    post_list = Post.view_manager.posts_for_thread(thread_id, request.user)
    if get_user_settings(request.user).reverse_posts:
        post_list = post_list.order_by('-odate')

    render_dict.update({
            'posts': post_list,
            'thr': thr,
            'postform': postform,
            })
    
    return render_to_response('snapboard/thread.html',
            render_dict,
            context_instance=RequestContext(request, processors=extra_processors))

@login_required
def edit_post(request, original, next=None):
    '''
    Edit an existing post.decorators in python
    '''
    if not request.method == 'POST':
        raise Http404

    try:
        orig_post = Post.view_manager.get(pk=int(original))
    except Post.DoesNotExist:
        raise Http404
        
    if orig_post.user != request.user or not orig_post.thread.category.can_post(request.user):
        raise PermissionError

    postform = PostForm(request.POST)
    if postform.is_valid():
        # create the post
        post = Post(
                user = request.user,
                thread = orig_post.thread,
                text = postform.cleaned_data['post'],
                previous = orig_post,
                )
        post.save()
        #post.private = orig_post.private.all()
        #post.is_private = orig_post.is_private
        post.save()

        orig_post.revision = post
        orig_post.save()

        div_id_num = post.id
    else:
        div_id_num = orig_post.id

    try:
        next = request.POST['next'].split('#')[0] + '#snap_post' + str(div_id_num)
    except KeyError:
        next = reverse('snapboard_locate_post', args=(orig_post.id,))

    return HttpResponseRedirect(next)

##
# Should new discussions be allowed to be private?  Leaning toward no.
@login_required
def new_thread(request, cat_id):
    '''
    Start a new discussion.
    '''
    category = get_object_or_404(Category, pk=cat_id)
    if not category.can_create_thread(request.user):
        raise PermissionError

    if request.POST:
        threadform = ThreadForm(request.POST)
        if threadform.is_valid():
            # create the thread
            thread = Thread(
                    subject = threadform.cleaned_data['subject'],
                    category = category,
                    )
            thread.save()

            # create the post
            post = Post(
                    user = request.user,
                    thread = thread,
                    text = threadform.cleaned_data['post'],
                    )
            post.save()

            # redirect to new thread
            return HttpResponseRedirect(reverse('snapboard_thread', args=(thread.id,)))
    else:
        threadform = ThreadForm()

    return render_to_response('snapboard/newthread.html',
            {
            'form': threadform,
            },
            context_instance=RequestContext(request, processors=extra_processors))

@login_required
def favorite_index(request):
    '''
    This page shows the threads/discussions that have been marked as 'watched'
    by the user.
    '''
    thread_list = filter(lambda t: t.category.can_view(request.user), Thread.view_manager.get_favorites(request.user))

    render_dict = {'title': _("Watched Discussions"), 'threads': thread_list}

    return render_to_response('snapboard/thread_index.html',
            render_dict,
            context_instance=RequestContext(request, processors=extra_processors))

"""
@login_required
def private_index(request):
    thread_list = [thr for thr in Thread.view_manager.get_private(request.user) if thr.category.can_read(request.user)]

    render_dict = {'title': _("Discussions with private messages to you"), 'threads': thread_list}

    return render_to_response('snapboard/thread_index.html',
            render_dict,
            context_instance=RequestContext(request, processors=extra_processors))
""";

def category_thread_index(request, cat_id):
    try:
        cat = Category.objects.get(pk=cat_id)
        if not cat.can_read(request.user):
            raise PermissionError
        thread_list = Thread.view_manager.get_category(cat_id)
        render_dict = ({'title': ''.join((_("City: "), cat.label)), 'category': cat, 'threads': thread_list})
    except Category.DoesNotExist:
        raise Http404
    return render_to_response('snapboard/thread_index.html',
            render_dict,
            context_instance=RequestContext(request, processors=extra_processors))

def thread_index(request):
    if request.user.is_authenticated():
        # filter on user prefs
        thread_list = Thread.view_manager.get_user_queryset(request.user)
    else:
        thread_list = Thread.view_manager.get_queryset()
    thread_list = filter(lambda t: t.category.can_view(request.user), thread_list)
    render_dict = {'title': _("Recent Posts"), 'threads': thread_list}
    return render_to_response('snapboard/thread_index.html',
            render_dict,
            context_instance=RequestContext(request, processors=extra_processors))

def locate_post(request, post_id):
    '''
    Redirects to a post, given its ID.
    '''
    post = get_object_or_404(Post, pk=post_id)
    if not post.thread.category.can_read(request.user):
        raise PermissionError
    #if post.is_private and not (post.user==request.user or post.private.filter(pk=request.user.id).count()):
        #raise PermissionError
    # Count the number of visible posts before the one we are looking for, 
    # as well as the total
    total = post.thread.count_posts(request.user)
    preceding_count = post.thread.count_posts(request.user, before=post.date)
    # Check the user's settings to locate the post in the various pages
    settings = get_user_settings(request.user)
    ppp = settings.ppp
    if total < ppp:
        page = 1
    elif settings.reverse_posts:
        page = (total - preceding_count - 1) // ppp + 1
    else:
        page = preceding_count // ppp + 1
    return HttpResponseRedirect('%s?page=%i#snap_post%i' % (reverse('snapboard_thread', args=(post.thread.id,)), page, post.id))

def category_index(request):
    return render_to_response('snapboard/category_index.html',
            {
            'cat_list': [c for c in Category.objects.all() if c.can_view(request.user)],
            },
            context_instance=RequestContext(request, processors=extra_processors))

@login_required
def edit_settings(request):
    '''
    Allow user to edit his/her profile. Requires login.
    '''
    try:
        userdata = UserSettings.objects.get(user=request.user)
    except UserSettings.DoesNotExist:
        userdata = UserSettings.objects.create(user=request.user)
    if request.method == 'POST':
        form = UserSettingsForm(request.POST, instance=userdata, user=request.user)
        if form.is_valid():
            form.save(commit=True)
    else:
        form = UserSettingsForm(instance=userdata, user=request.user)
    return render_to_response(
            'snapboard/edit_settings.html',
            {'form': form},
            context_instance=RequestContext(request, processors=extra_processors))

@login_required
def manage_group(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    if not group.has_admin(request.user):
        raise PermissionError
    render_dict = {'group': group, 'invitation_form': InviteForm()}
    if request.GET.get('manage_users', False):
        render_dict['users'] = group.users.all()
    elif request.GET.get('manage_admins', False):
        render_dict['admins'] = group.admins.all()
    elif request.GET.get('pending_invitations', False):
        render_dict['pending_invitations'] = group.sb_invitation_set.filter(accepted=None)
    elif request.GET.get('answered_invitations', False):
        render_dict['answered_invitations'] = group.sb_invitation_set.exclude(accepted=None)
    return render_to_response(
            'snapboard/manage_group.html',
            render_dict,
            context_instance=RequestContext(request, processors=extra_processors))

@login_required
def invite_user_to_group(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    if not group.has_admin(request.user):
        raise PermissionError
    if request.method == 'POST':
        form = InviteForm(request.POST)
        if form.is_valid():
            invitee = form.cleaned_data['user']
            if group.has_user(invitee):
                invitation = None
                request.user.message_set.create(message=_('The user %s is already a member of this group.') % invitee)
            else:
                invitation = Invitation.objects.create(
                        group=group,
                        sent_by=request.user,
                        sent_to=invitee)
                request.user.message_set.create(message=_('A invitation to join this group was sent to %s.') % invitee)
            return render_to_response('snapboard/invite_user.html',
                    {'invitation': invitation, 'form': InviteForm(), 'group': group},
                    context_instance=RequestContext(request, processors=extra_processors))
    else:
        form = InviteForm()
    return render_to_response('snapboard/invite_user.html',
            {'form': form, 'group': group},
            context_instance=RequestContext(request, processors=extra_processors))

@login_required
def remove_user_from_group(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    if not group.has_admin(request.user):
        raise PermissionError
    if request.method == 'POST':
        done = False
        user = User.objects.get(pk=int(request.POST.get('user_id', 0)))
        only_admin = int(request.POST.get('only_admin', 0))
        if not only_admin and group.has_user(user):
            group.users.remove(user)
            done = True
        if group.has_admin(user):
            group.admins.remove(user)
            if notification:
                notification.send(
                    [user],
                    'group_admin_rights_removed',
                    {'group': group})
            done = True
        if done:
            if only_admin:
                request.user.message_set.create(message=_('The admin rights of user %s were removed for the group.') % user)
            else:
                request.user.message_set.create(message=_('User %s was removed from the group.') % user)
        else:
            request.user.message_set.create(message=_('There was nothing to do for user %s.') % user)
    else:
        raise Http404
    return HttpResponse('ok')

@login_required
def grant_group_admin_rights(request, group_id):
    '''
    Although the Group model allows non-members to be admins, this view won't 
    let it.
    '''
    group = get_object_or_404(Group, pk=group_id)
    if not group.has_admin(request.user):
        raise PermissionError
    if request.method == 'POST':
        user = User.objects.get(pk=int(request.POST.get('user_id', 0)))
        if not group.has_user(user):
            request.user.message_set.create(message=_('The user %s is not a group member.') % user)
        elif group.has_admin(user):
            request.user.message_set.create(message=_('The user %s is already a group admin.') % user)
        else:
            group.admins.add(user)
            request.user.message_set.create(message=_('The user %s is now a group admin.') % user)
            if notification:
                notification.send(
                    [user],
                    'group_admin_rights_granted',
                    {'group': group})
                notification.send(
                    list(group.admins.all()),
                    'new_group_admin',
                    {'new_admin': user, 'group': group})
    else:
        raise Http404
    return HttpResponse('ok')

@login_required
def discard_invitation(request, invitation_id):
    if not request.method == 'POST':
        raise Http404
    invitation = get_object_or_404(Invitation, pk=invitation_id)
    if not invitation.group.has_admin(request.user):
        raise PermissionError
    was_pending = invitation.accepted is not None
    invitation.delete()
    if was_pending:
        request.user.message_set.create(message=_('The invitation was cancelled.'))
    else:
        request.user.message_set.create(message=_('The invitation was discarded.'))
    return HttpResponse('ok')

@login_required
def answer_invitation(request, invitation_id):
    invitation = get_object_or_404(Invitation, pk=invitation_id)
    if request.user != invitation.sent_to:
        raise Http404
    form = None
    if request.method == 'POST':
        if invitation.accepted is not None:
            return HttpResponseRedirect('')
        form = AnwserInvitationForm(request.POST)
        if form.is_valid():
            if int(form.cleaned_data['decision']):
                invitation.group.users.add(request.user)
                invitation.accepted = True
                request.user.message_set.create(message=_('You are now a member of the group %s.') % invitation.group.name)
                if notification:
                    notification.send(
                        list(invitation.group.admins.all()),
                        'new_group_member',
                        {'new_member': request.user, 'group': invitation.group})
            else:
                invitation.accepted = False
                request.user.message_set.create(message=_('The invitation has been declined.'))
            invitation.response_date = datetime.datetime.now()
            invitation.save()
    elif invitation.accepted is None:
        form = AnwserInvitationForm()
    return render_to_response('snapboard/invitation.html',
            {'form': form, 'invitation': invitation},
            context_instance=RequestContext(request, processors=extra_processors))

def get_user_settings(user):
    if not user.is_authenticated():
        return DEFAULT_USER_SETTINGS
    try:
        return user.sb_usersettings
    except UserSettings.DoesNotExist:
        return DEFAULT_USER_SETTINGS

@login_required
def profile(request, userid):
    context = RequestContext(request, processors=extra_processors)
    
    if not request.user.is_authenticated():
        # Change to login form at some point
        return HttpResponseRedirect(reverse('snapboard_index'))
    
    username = User.objects.get(id=userid).username

    if request.method == 'POST':
        thisProfile = UserProfile.objects.get(user_id=userid)
        profile_form = UserProfileForm(data=request.POST, instance=thisProfile)
        if profile_form.is_valid():
            profile_form.save(commit=True)
            #return HttpResponseRedirect(reverse('update_profile_success'))
    else: # Request method is a GET, i.e. profile view
        try:
            thisProfile = UserProfile.objects.get(user_id=userid)
            if int(userid) == request.user.id:
                profile_form = UserProfileForm(instance=thisProfile)
            else:
                profile_form = UserProfile.objects.get(user_id=userid)
        except UserSettings.DoesNotExist:
            profile_form = None
            
    responseUrl = "snapboard/profile.html"
    if profile_form is None:
        responseUrl = "snapboard/profile.html"
        username = "User does not exist."
    
    return render_to_response(
            responseUrl,
            {'profile_form': profile_form, 'userid': userid, 'username': username, 'inst': thisProfile},
            context)

def register(request):
    # Like before, get the request's context.
    context = RequestContext(request)

    # A boolean value for telling the template whether the registration was successful.
    # Set to False initially. Code changes value to True when registration succeeds.
    registered = False

    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
        # Attempt to grab information from the raw form information.
        # Note that we make use of both UserForm and UserProfileForm.
        user_form = UserForm(data=request.POST)
        #profile_form = UserProfileForm(data=request.POST)
    
        # If the two forms are valid...
        if user_form.is_valid(): # and profile_form.is_valid():
            # Save the user's form data to the database.
            user = user_form.save()

            # Now we hash the password with the set_password method.
            # Once hashed, we can update the user object.
            user.set_password(user.password)
            user.save()

            # Now sort out the UserProfile instance.
            # Since we need to set the user attribute ourselves, we set commit=False.
            # This delays saving the model until we're ready to avoid integrity problems.
            #profile = profile_form.save(commit=False)
            #profile.user = user
            #profile.rating_votes = 0
            
            # Now we save the UserProfile model instance.
            #profile.save()
            #print "Prof Saved."

            # Update our variable to tell the template registration was successful.
            registered = True          

        # Invalid form or forms - mistakes or something else?
        # Print problems to the terminal.
        # They'll also be shown to the user.
        else:
            print user_form.errors #, profile_form.errors

    # Not a HTTP POST, so we render our form using two ModelForm instances.
    # These forms will be blank, ready for user input.
    else:
        user_form = UserForm()
        #profile_form = UserProfileForm()

    # Render the template depending on the context.
    return render_to_response(
            'snapboard/register.html',
            {'user_form': user_form, 'registered': registered}, #'profile_form': profile_form, 
            context)

def user_login(request):
    # Like before, obtain the context for the user's request.
    context = RequestContext(request)

    # If the request is a HTTP POST, try to pull out the relevant information.
    if request.method == 'POST':
        # Gather the username and password provided by the user.
        # This information is obtained from the login form.
        username = request.POST['username']
        password = request.POST['password']

        # Use Django's machinery to attempt to see if the username/password
        # combination is valid - a User object is returned if it is.
        user = authenticate(username=username, password=password)

        # If we have a User object, the details are correct.
        # If None (Python's way of representing the absence of a value), no user
        # with matching credentials was found.
        if user:
            # Is the account active? It could have been disabled.
            if user.is_active:
                # If the account is valid and active, we can log the user in.
                # We'll send the user back to the homepage.
                login(request, user)
                return HttpResponseRedirect('/')
            else:
                # An inactive account was used - no logging in!
                return HttpResponse("Your Snapboard account is disabled.")
        else:
            # Bad login details were provided. So we can't log the user in.
            print "Invalid login details: {0}, {1}".format(username, password)
            return HttpResponse("Invalid login details supplied.")

    # The request is not a HTTP POST, so display the login form.
    # This scenario would most likely be a HTTP GET.
    else:
        login_form = LoginForm(data=request.POST)
        # No context variables to pass to the template system, hence the
        # blank dictionary object...
        return render_to_response('snapboard/signin.html', {'login_form': login_form}, context)

def _brand_view(func):
    '''
    Mark a view as belonging to SNAPboard.

    Allows the UserBanMiddleware to limit the ban to SNAPboard in larger 
    projects.
    '''
    setattr(func, '_snapboard', True)

_brand_view(rpc)
_brand_view(thread)
_brand_view(edit_post)
_brand_view(new_thread)
_brand_view(favorite_index)
#_brand_view(private_index)
_brand_view(category_thread_index)
_brand_view(thread_index)
_brand_view(locate_post)
_brand_view(category_index)
_brand_view(edit_settings)
_brand_view(manage_group)
_brand_view(invite_user_to_group)
_brand_view(remove_user_from_group)
_brand_view(grant_group_admin_rights)
_brand_view(discard_invitation)
_brand_view(answer_invitation)

# vim: ai ts=4 sts=4 et sw=4
