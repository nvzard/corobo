from errbot.backends.test import TestBot

def plugin_testbot(klass, plugin_name, loglevel, config=None):
    config = config if config else dict()
    testbot = TestBot(loglevel=loglevel, extra_config=config)
    testbot.start()
    plug = klass(testbot.bot, plugin_name)
    return plug, testbot
