import logging
from collections import namedtuple
from distutils.util import strtobool
import pydbus
from gi.repository import GLib
# for some reason the current pydbus version doesn't provide Variant, so we
# need to import it explicitly
from gi.repository.GLib import Variant


class DBus2VDR(object):
    Plugin = namedtuple("Plugin", ['name', 'version'])
    vdr_isrunning = False
    logger = logging.getLogger(__name__)
    EPGEntry = namedtuple(
        "EPGEntry",
        [
            'ChannelID',
            'EventID',
            'Title',
            'ShortText',
            'Description',
            'StartTime',
            'EndTime',
            'Duration',
            'Vps',
            'RunningStatus',
            'ParentalRating',
            'HasTimer',
            'ContentID',
            'Content'
        ]
    )

    SetupEntry = namedtuple(
        "SetupEntry",
        [
            'name',
            'value',
            'min',
            'max'
        ]
    )

    class Recording(object):
        def __init__(self, recording):
            self.id, data = recording
            self.__dict__.update(dict((key, value) for key, value in (
                item for item in data)))

    class _BasicInterface(object):
        def __init__(self, bus=None, vdr_name='de.tvdr.vdr'):
            if bus is None:
                self.bus = pydbus.SystemBus()
            else:
                self.bus = bus
            self.vdr_name = vdr_name
            self._proxy = self.bus.get(vdr_name, self.object_path)

        @staticmethod
        def autovariant(argument):
            if isinstance(argument, str):
                variant_type = 's'
            elif isinstance(argument, int):
                variant_type = 'i'
            # do we really need additional datatypes?
            elif isinstance(argument, list):
                if all(map(lambda x: isinstance(x, str), argument)):
                    variant_type = 'as'
                elif all(map(lambda x: isinstance(x, int), argument)):
                    variant_type = 'ai'
            return Variant(variant_type, argument)

    class _Plugins(_BasicInterface):
        object_path = "/Plugins"

        def list(self):
            return [DBus2VDR.Plugin(*attributes) for attributes in self.List()]

        def List(self):
            return self._proxy.List()

        def SVDRPCommand(self, plugin_name, command, parameter=""):
            plugin_name = plugin_name.replace('-', '_')
            object_path = self.object_path + "/" + plugin_name
            plugin_proxy = self.bus.get(self.vdr_name, object_path)
            return plugin_proxy.SVDRPCommand(str(command), str(parameter))

        def Service(self, plugin_name, id_value, data=""):
            plugin_name = plugin_name.replace('-', '_')
            object_path = self.object_path + "/" + plugin_name
            plugin_proxy = self.bus.get(self.vdr_name, object_path)
            return plugin_proxy.Service(str(id_value), str(data))

    class _Channels(_BasicInterface):
        object_path = "/Channels"

        def __len__(self):
            return self._proxy.Count()

        def __getitem__(self, index):
            if index >= len(self) or index < 0:
                raise IndexError("invalid index for channel")
            return self.GetFromTo(index, index)

        def Count(self):
            return self._proxy.Count()

        def Current(self):
            return self._proxy.Current()

        def GetFromTo(self, from_index=0, to_index=None):
            if to_index is None:
                to_index = self.Count()
            return self._proxy.GetFromTo(from_index, to_index)

        def List(self, arg=""):
            return self._proxy.List(arg)

    class _Devices(_BasicInterface):
        object_path = "/Devices"
        device = namedtuple('Device', ["index", "number", "hasDecoder",
                                       "isPrimary", "name"])

        @property
        def primary_device(self):
            return self.GetPrimary()

        def GetPrimary(self):
            return self._proxy.GetPrimary()

        def GetNullDevice(self):
            index = self._proxy.GetNullDevice()
            if index > -1:
                return index
            else:
                raise ValueError(('nulldevice not found. '
                                  'start dbus2vdr with --nulldevice'))

        def RequestPrimary(self, index):
            return self._proxy.RequestPrimary(index)

        def request_primary_by_name(self, name):
            devices = self.list()
            try:
                index = next(
                    device.index for device in devices if device.name == name)
            except StopIteration:
                raise ValueError("%s is not available" % name)
            else:
                return self.RequestPrimary(index)

        def list(self):
            return [self.device(*dev) for dev in self.List()]

        def List(self):
            return self._proxy.List()

    class _EPG(_BasicInterface):
        object_path = "/EPG"

        def DisableScanner(self, timeout=3600):
            return self._proxy.DisableScanner(int(timeout))

        def EnableScanner(self):
            return self._proxy.EnableScanner()

        def ClearEpg(self, channel, timeout):
            return self._proxy.ClearEPG(str(channel), int(timeout))

        def PutEntry(self, entry):
            return self._proxy.PutEntry(entry)

        def PutFile(self, filename):
            return self._proxy.PutFile(filename)

        def Now(self, channel):
            return self._proxy.Now(str(channel))

        def now(self, channel):
            for entry in self.Now(channel)[2]:
                return DBus2VDR.EPGEntry(*entry)

        def Next(self, channel):
            return self._proxy.Next(str(channel))

        def next(self, channel):
            for entry in self.Now(channel)[2]:
                return DBus2VDR.EPGEntry(*entry)

        def At(self, channel, time):
            return self._proxy.At(str(channel), int(time))

        def at(self, channel, time):
            for entry in self.At(channel, time)[2]:
                return DBus2VDR.EPGEntry(*entry)

    class _Recordings(_BasicInterface):
        object_path = "/Recordings"

        def Update(self):
            return self._proxy.Update()

        def Get(self, recording):
            return self._proxy.Get(
                self.autovariant(recording))

        def List(self):
            return self._proxy.List()

        def Play(self, recording, start=-1):
            return self._proxy.Play(
                self.autovariant(recording),
                self.autovariant(start),
                )

    class _Remote(_BasicInterface):
        object_path = "/Remote"

        def Enable(self):
            return self._proxy.Enable()

        def Disable(self):
            return self._proxy.Disable()

        def Status(self):
            return self._proxy.Status()

        def HitKey(self, key):
            return self._proxy.HitKey(key)

        def HitKeys(self, keys):
            return self._proxy.HitKeys(keys)

        def AskUser(self, question, answers=[]):
            return self._proxy.AskUser(str(question), answers)

        def CallPlugin(self, plugin):
            return self._proxy.CallPlugin(str(plugin))

        def SwitchChannel(self, chan):
            return self._proxy.SwitchChannel(str(chan))

        def GetVolume(self):
            current_volume, muted = self._proxy.GetVolume()
            return current_volume, muted

        def SetVolume(self, vol):
            if isinstance(vol, int):
                vol = Variant('i', vol)
            elif isinstance(vol, str):
                vol = Variant('s', vol)
            return self._proxy.SetVolume(vol)

    class _Setup(_BasicInterface):
        object_path = "/Setup"

        def List(self):
            return self._proxy.List()

        def list(self):
            setup_entries = []
            for entry in self.List():
                name, options = entry
                if isinstance(options, int):
                    value = options
                    maximum = None
                    minimum = None
                elif len(options) == 3:
                    value, minimum, maximum = options
                elif len(options) == 2:
                    value, maximum = options
                    minimum = None

                setup_entry = DBus2VDR.SetupEntry(
                    name, value, minimum, maximum)
                setup_entries.append(setup_entry)
            return setup_entries

        def Get(self, option):
            """
            return the value, ok code (900), an a string "getting {option}"
            """
            return self._proxy.Get(str(option))

        def get(self, option):
            value, response_code, response_string = self.Get(option)
            if response_code == 900:
                return value
            else:
                raise ValueError(response_string)

        def Set(self, option, value):
            return self._proxy.Set(str(option), self.autovariant(value))

        def Del(self, option):
            return self._proxy.Del(str(option))

    class _Shutdown(_BasicInterface):
        object_path = "/Shutdown"

        def ConfirmShutdown(self, ignore_user=True):
            """
            returns: reply code, reason as string,
                     return code of shutdown-wapper, output of shutdown-wrapper
            possible reply codes:
            250: vdr is ready for shutdown
            550: vdr is not ready for shutdown (unknown reason)
            901: user is active
            902: cutter is active
            903: recording is active
            904: recording is active in the near future
            905: some plugin is active
            906: some plugin will wakeup vdr in the near future
            990: (reply message contains SHUTDOWNCMD)
            991: (reply message contains TRY_AGAIN of the shutdown-hooks)
            992: (reply message contains ABORT_MESSAGE of the shutdown-hooks)
            999: shutdown-hook returned a non-zero exit code
            """
            return self._proxy.ConfirmShutdown(strtobool(ignore_user))

        def ManualStart(self):
            return self._proxy.ManualStart()

        def NextWakeupTime(self):
            return self._proxy.NextWakeupTime()

        def SetUserInactive(self):
            return self._proxy.SetUserInactive()

    class _Skin(_BasicInterface):
        object_path = "/Skin"

        def QueueMessage(self, msg):
            return self._proxy.QueueMessage(str(msg))

        def ListSkins(self):
            return self._proxy.ListSkins()

        def CurrentSkin(self):
            return self._proxy.CurrentSkin()

        def SetSkin(self, skin_name):
            return self._proxy.CurrentSkin(str(skin_name))

    class _Status(_BasicInterface):
        object_path = "/Status"

        def IsReplaying(self):
            return self._proxy.IsReplaying()

    class _Signals(object):
        def __init__(self, bus=None, vdr_name='de.tvdr.vdr'):
            if bus is None:
                self.bus = pydbus.SystemBus()
            else:
                self.bus = bus
            self.vdr_name = vdr_name

        def _subscribeSignal(self, object, interface, signal=None,
                             signal_fired=None):
            return self.bus.subscribe(object=object,
                                      iface=(self.vdr_name + interface),
                                      signal=signal,
                                      signal_fired=signal_fired)

        def subscribeStatusSignal(self, callback):
            """
            Subscribe to all Status signals. The given callback function must
            acept the following arguments: sender, object, iface, signal, params
            returns a subscription object. Use it's unsubscribe() method (or a
            context manager like with) to stop receiving signals when done.
            """
            return self._subscribeSignal(object="/Status",
                                         interface=".status",
                                         signal_fired=callback)

        def subscribeAskUserSelect(self, callback):
            return self._subscribeSignal(object="/Remote",
                                         interface=".remote",
                                         signal="AskUserSelect",
                                         signal_fired=callback)

        def subscribeChannelSwitch(self, callback):
            return self._subscribeSignal(object="/Status",
                                         interface=".status",
                                         signal="ChannelSwitch",
                                         signal_fired=callback)

        def subscribeRecording(self, callback):
            return self._subscribeSignal(object="/Status",
                                         interface=".status",
                                         signal="Recording",
                                         signal_fired=callback)

        def subscribeReplaying(self, callback):
            return self._subscribeSignal(object="/Status",
                                         interface=".status",
                                         signal="Replaying",
                                         signal_fired=callback)

        def subscribeSetAudioChannel(self, callback):
            return self._subscribeSignal(object="/Status",
                                         interface=".status",
                                         signal="SetAudioChannel",
                                         signal_fired=callback)

        def subscribeSetAudioTrack(self, callback):
            return self._subscribeSignal(object="/Status",
                                         interface=".status",
                                         signal="SetAudioTrack",
                                         signal_fired=callback)

        def subscribeSetSubtitleTrack(self, callback):
            return self._subscribeSignal(object="/Status",
                                         interface=".status",
                                         signal="SetSubtitleTrack",
                                         signal_fired=callback)

        def subscribeSetVolume(self, callback):
            return self._subscribeSignal(object="/Status",
                                         interface=".status",
                                         signal="SetVolume",
                                         signal_fired=callback)

        def subscribeTimerChange(self, callback):
            return self._subscribeSignal(object="/Status",
                                         interface=".status",
                                         signal="TimerChange",
                                         signal_fired=callback)

        def subscribeVDRStatus(self, callback):
            return self._subscribeSignal(object="/vdr",
                                         interface=".vdr",
                                         signal_fired=callback
                                         )

        def subscribeVDRReady(self, callback):
            return self._subscribeSignal(object="/vdr",
                                         interface=".vdr",
                                         signal="Ready",
                                         signal_fired=callback)

        def subscribeVDRStart(self, callback):
            return self._subscribeSignal(object="/vdr",
                                         interface=".vdr",
                                         signal="Start",
                                         signal_fired=callback)

        def subscribeVDRStop(self, callback):
            return self._subscribeSignal(object="/vdr",
                                         interface=".vdr",
                                         signal="Stop",
                                         signal_fired=callback)

    class _Timers(_BasicInterface):
        object_path = "/Timers"

        def List(self):
            return self._proxy.List()

        def ListDetailed(self):
            return self._proxy.ListDetailed()

        def Next(self):
            return self._proxy.Next()

        def New(self, timer):
            return self._proxy.New(str(timer))

        def Delete(self, timer_id):
            return self._proxy.Delete(int(timer_id))

    class _VDR(_BasicInterface):
        object_path = "/vdr"

        def Status(self):
            return self._proxy.Status()

    def __init__(self, bus=None, instance_id=0, watchdog=False):
        self.isinitialized = False
        self.status_change_callbacks = []
        self.vdr_name = "de.tvdr.vdr" + (
            str(instance_id) if instance_id else "")
        self.bus = bus if bus else pydbus.SystemBus()
        self.dbus = self.bus.get('.DBus')
        if watchdog is True:
            self.Signals = self._Signals(self.bus, self.vdr_name)
            self._start_cb = self.Signals.subscribeVDRReady(self._startup)
            self._stop_cb = self.Signals.subscribeVDRStop(self._stop)
            self.dbus.NameOwnerChanged.connect(self._onNameOwnerChanged)
            self.Signals = self._Signals(self.bus, self.vdr_name)
        try:
            if self.vdr_name in self.dbus.ListNames() or watchdog is False:
                self._startup()
        except Exception as e:
            logging.exception(e)

    def _startup(self, *args):
        self.vdr_isrunning = True
        if not self.isinitialized:
            for item in ("_Plugins", "_Remote", "_Recordings", "_VDR",
                         "_Timers", "_Status", "_Skin", "_Shutdown",
                         "_Devices", "_EPG", "_Signals", "_Setup",
                         "_Channels"):
                obj = getattr(self, item)(bus=self.bus)
                setattr(self, item.lstrip("_"), obj)
            self.isinitialized = True
        self._on_status_change()

    def _stop(self, *args):
        self.vdr_isrunning = False
        self._on_status_change()

    def _onNameOwnerChanged(self, first, _, last):
        if self.vdr_isrunning and first == self.vdr_name and not last:
            self.vdr_isrunning = False
            self._on_status_change()

    def _on_status_change(self):
        self.logger.info("VDR Status: %s",
                         "running" if self.vdr_isrunning else "stopped")
        for callback in self.status_change_callbacks:
            callback(self.vdr_isrunning)


def print_debug_status(*args, **kwargs):
    print(args, kwargs)

if __name__ == '__main__':
    loop = GLib.MainLoop()
    dbus2vdr = DBus2VDR()
    with dbus2vdr.Status.subscribeVDRStatus(print_debug_status) as s:
        try:
            loop.run()
        except KeyboardInterrupt:
            loop.quit()
