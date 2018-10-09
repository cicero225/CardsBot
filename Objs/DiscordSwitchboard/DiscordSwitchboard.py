"""A class that acts like a switchboard for discord messages. The class can be recursive.

Python 3.5+ only.

Usage:

1. Set up the DiscordSwitchboard object. Make sure to include the right functor outputs.
2. Include an await switchboard.on_message(message) somewhere in your discord client on_message (or ensure_future if you prefer)
3. Make sure to hold onto a reference to the object to keep it alive/modify it as desired.
4, Each switchboard internally can only process if/then for messages one-by-one. If you have two users you are _certain_ cannot possibly collide with each other, then
   spin more than one switchboard onto multiple parallel threads. This evil is necessary to ensure users get reliable switchboard behavior.

"""
from collections import OrderedDict
from enum import Enum
from functools import partial
import asyncio
import discord
import threading

class PriorityLevel(Enum):
    PRIORITY = 1
    GENERAL = 2
    GENERAL_BLOCKING = 3
    FALLBACK = 4

# A decorator. Function must have no return value.
def SafeLock(func):
    def new_func(self, *args, **kwargs):
        self.RunOrDeferIfActive(partial(func, self, *args, **kwargs))
    return new_func
    
class DiscordSwitchboard:
    def __init__(self):
        self.lock = threading.Lock()
        # Internal only.
        self._overriding = OrderedDict()
        # All conditional relays are of the form OrderedDict[id: (matching_coroutine(message)->bool, output_coroutine(message) OR DiscordSwitchboard), Closure (run when done)].
        # where id is id(matching_coroutine) to facilitate look-up. Hold onto the functor or id if you wish to remove/modify this later. (id is returned by all relevant utility functions)
        # Note that for priority_relay the output_coroutine is expect to return a value (None if the output "passes (chooses to do nothing and should be passed to next ouput)", False if the message was not processed, True if it was processed succesfully.)
        
        # Note that id is for the _coroutine_, not the Task. Use functools.partial if you wish to anonymize a coroutine.
        
        # You are free to add your own matcher/output, but the utility functions are recommended for this purpose. If you do do so, remember to take the lock first.
        
        # For priority relay
        self.priority_relay = OrderedDict()  # Meant for dedicated lines. Checked _first_, and the first matching_coroutine that returns true will be the only one to output (unless it returns None). First come, first served.
        self.general_relay = OrderedDict()  # Checked after priority. All matches are processed and will output asynchronously (outputs will not block each other, but all matches are checked first)
        self.blocking_relay = OrderedDict()  # Checked after general relay. Matches and outputs are processed in order and will block. First come, first served.
        # list[output_coroutine(message)]  # Run last, only if nothing else matched. Unconditional, asynchronous. Keys are id(output)
        self.fallback_relay = OrderedDict() 
        self.priority_dict = {PriorityLevel.PRIORITY: self.priority_relay,
                              PriorityLevel.GENERAL: self.general_relay,
                              PriorityLevel.GENERAL_BLOCKING: self.blocking_relay,
                              PriorityLevel.FALLBACK: self.fallback_relay}
        
        # Needed to navigate the internal locks. Specifically, this should be locked first and checked before taking the main lock, for any function that isn't on_message. This is
        # inelegant but Python lacks better locking things for this.
        self.active_lock = threading.Lock()
        self._is_active = False
        self._deferred_actions = []
        self._deferred_actions_async = []
        
    async def __call__(self, message):
        await on_message(message)
    
    def RunOrDeferIfActive(self, func):
        with self.active_lock:
            if self._is_active:
                self._deferred_actions.append(func)
            else:
                with self.lock:
                    func()

    # returns False if the message is not processed by anything, or the output of a successful priority_relay output, or True if something processed the message.
    # priority_relay outputs can also return False or None if they wish to signal a failure (which will also prevent the operation of all closures, self-removal, etc.)
    async def on_message(self, message):
        with self.lock:  # This is unfortunate but necessary.
            with self.active_lock:
                self._is_active = True
            return_val = None
            while True:
                for matcher, output, closure_list in self._overriding.values():
                    if await matcher(message):
                        return_val = await output(message)
                        if return_val is not None and return_val:
                            if closure_list is not None:
                                for closure in closure_list:
                                    await closure()
                            break
                if return_val is not None:
                    break
                for matcher, output, closure_list in self.priority_relay.values():
                    if await matcher(message):
                        return_val = await output(message)
                        if return_val is not None:
                            if return_val:
                                if closure_list is not None:
                                    for closure in closure_list:
                                        await closure()
                                break
                            else:
                                break
                        
                if return_val is not None:
                    break
                any_found = False
                
                # This is awkward but necessary.
                value_list = list(self.general_relay.values())
                matchers = [asyncio.ensure_future(value[0](message)) for value in value_list]
                matches = await asyncio.gather(*matchers)
                all_closures = []
                for index, match in enumerate(matches):
                    if match:
                        asyncio.run_coroutine_threadsafe(value_list[index][1](message), asyncio.get_event_loop())
                        if value_list[index][2]:
                            all_closures.extend(value_list[index][2])
                        any_found = True
                
                for matcher, output, closure_list in self.blocking_relay.values():
                    if await matcher(message):
                        await output(message)
                        if closure_list is not None:
                            all_closures.extend(closure_list)
                        any_found = True

                if not self.fallback_relay:
                    for closure in all_closures:
                        asyncio.run_coroutine_threadsafe(closure(), asyncio.get_event_loop())
                    return_val = any_found
                    break
                
                if not any_found:
                    for output, closure_list in self.fallback_relay.values():
                        asyncio.run_coroutine_threadsafe(output(message), asyncio.get_event_loop())
                        if closure_list is not None:
                            all_closures.extend(closure_list)
                for closure in all_closures:
                    asyncio.run_coroutine_threadsafe(closure(), asyncio.get_event_loop())
                return_val = True
                break
            with self.active_lock:
                self._is_active = False
                for action in self._deferred_actions:
                    action()
                self._deferred_actions.clear()
                for action in self._deferred_actions_async:
                    await action()
                self._deferred_actions_async.clear()
        
    
    @staticmethod
    async def message_ignored(message):
        return False
    
    @staticmethod
    async def author_check(id, message, polarity=True):
        return (message.author.id == id) == polarity
        
    @staticmethod
    async def start_check(start, message, polarity=True):
        return (message.content.lower().startswith(start)) == polarity

    @staticmethod
    async def channel_check(channel_id, message, polarity=True):
        return (message.channel.id == channel_id) == polarity     

    @staticmethod
    async def mention_check(mentions, message, polarity=True):
        return any(x.id == mentions for x in message.mentions) == polarity
        
    @staticmethod
    async def private_check(message, polarity=True):
        return message.channel.is_private == polarity
    
    # Not Safe, used as closures.
    def _RemoveOutput(self, id, priority):
        del self.priority_dict[priority][id]
    
    async def _RemoveOutputAsync(self, id, priority):
        self._RemoveOutput(id, priority)
        
    def GetCheckers(self, author_id=None, channel_id=None, mentions=None, starts_with=None, is_private=None, polarity=True):
        checkers = []
        if channel_id is not None:
            checkers.append(partial(self.channel_check, channel_id, polarity=polarity))
        if starts_with is not None:
            checkers.append(partial(self.start_check, starts_with, polarity=polarity))
        if mentions is not None:
            checkers.append(partial(self.mention_check, mentions, polarity=polarity))
        if author_id is not None:
            checkers.append(partial(self.author_check, author_id, polarity=polarity))
        if is_private is not None:
            if is_private:
                checkers.append(partial(self.private_check, polarity=polarity))
            elif not is_private:
                checkers.append(partial(self.private_check, polarity=not polarity))
        return checkers
    
    @staticmethod
    async def CheckConditions(checkers, message):
        for checker in checkers:
            if not await checker(message):  # We are deliberately checking this sequentially, rather than asynchronously.
                return False
        return True
    
    # These affect this class, forcing the class to acknowledge only certain messages. Using named arguments is highly recommended.
    # Setting any=True causes this class to accept messages that meet _any_ condition, rather than all. Currently, this is irreversible.
    def MustHave(self, author_id=None, channel_id=None, mentions=None, starts_with=None, is_private=None, any=False):
        # If any = True, we want checkers to return positive checks then check until one is True. Otherwise, we want them to return negative checks.
        checkers = self.GetCheckers(author_id, channel_id, mentions, starts_with, is_private, polarity=any)
        if checkers:
            async def any_checker(message):
                for checker in checkers:
                    if await checker(message):
                        return (not any)  # If any, then this means a checker was True, which means we _don't_ want the message ignored. If not any, then this means we do want it ignored.
                return any
            def func():
                a_checker = lambda x: any_checker(x)
                self._overriding[id(a_checker)] = (a_checker, self.message_ignored, None)
            self.RunOrDeferIfActive(func)
    
    # These add outputs to the priority relay, with given conditions optionally. The conditions are ignored for the fallbacks.
    def RegisterOutput(self, output, priority, author_id=None, channel_id=None, mentions=None, starts_with=None, is_private=None, remove_self_when_done=False, remove_when_done=None, closure_list=None):
        if priority == PriorityLevel.FALLBACK:
            # Determine closures
            closure_list = [] if closure_list is None else closure_list
            if remove_self_when_done:
                closure_list.append(partial(self._RemoveOutputAsync, id(output), priority))
            if remove_when_done is not None:
                for closure_id, priority in remove_when_done:
                    closure_list.append(partial(self._RemoveOutputAsync, closure_id, priority))
            with self.lock:
                self.priority_dict[priority].append(output, closure_list)
            return id(output)
        checkers = self.GetCheckers(author_id, channel_id, mentions, starts_with, is_private)
        this_checker = partial(self.CheckConditions, checkers)
        # Determine closures
        closure_list = [] if closure_list is None else closure_list
        if remove_self_when_done:
            closure_list.append(partial(self._RemoveOutputAsync, id(this_checker), priority))
        if remove_when_done is not None:
            for closure_id, priority in remove_when_done:
                closure_list.append(partial(self._RemoveOutputAsync, closure_id, priority))  
        def func():
            self.priority_dict[priority][id(this_checker)] = (this_checker, output, closure_list)
        self.RunOrDeferIfActive(func)
        return id(this_checker)
        
    # Sometimes it is best to add a closure after the initial function is added, for organizational purposes. This enables that.
    @SafeLock
    def AddClosure(self, id, priority, closure):
        self.priority_dict[priority][id][2].append(closure)
    
    
    
    
    