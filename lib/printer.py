import sublime
import os
import unicodedata
import time

try:
    import MavensMate.config as config
    import MavensMate.util as util
    from .threads import ThreadTracker
except:
    import config
    import util
    from lib.threads import ThreadTracker

settings = sublime.load_settings('mavensmate.sublime-settings')

#class representing the MavensMate activity/debug panel in Sublime Text
class PanelPrinter(object):
    printers = {}

    def __init__(self):
        self.name = 'MavensMate-OutputPanel'
        self.visible = False
        self.hide_panel = settings.get('mm_hide_panel_on_success', 1)
        self.hide_time = settings.get('mm_hide_panel_time', 1)
        self.queue = []
        self.strings = {}
        self.just_error = False
        self.capture = False
        self.input = None
        self.input_start = None
        self.on_input_complete = None
        self.original_view = None

    @classmethod
    def get(cls, window_id):
        printer = cls.printers.get(window_id)
        if not printer:
            printer = PanelPrinter()
            printer.window_id = window_id
            printer.init()
            cls.printers[window_id] = printer
            printer.write('==============================================\n')
            printer.write('<---- MavensMate for Sublime Text v'+util.get_version_number()+' ---->\n')
            printer.write('==============================================\n')
        return printer

    def error(self, string):
        callback = lambda : self.error_callback(string)
        sublime.set_timeout(callback, 1)

    def error_callback(self, string):
        string = str(string)
        self.reset_hide()
        self.just_error = True
        sublime.error_message('MavensMate: ' + string)

    def hide(self, thread = None):
        settings = sublime.load_settings('mavensmate.sublime-settings')
        hide = settings.get('mm_hide_panel_on_success', True)
        if hide == True:
            hide_time = time.time() + float(hide)
            self.hide_time = hide_time
            sublime.set_timeout(lambda : self.hide_callback(hide_time, thread), int(hide * 300))

    def hide_callback(self, hide_time, thread):
        if thread:
            last_added = ThreadTracker.get_last_added(self.window_id)
            if thread != last_added:
                return
        if self.visible and self.hide_time and hide_time == self.hide_time:
            if not self.just_error:
                self.window.run_command('hide_panel')
            self.just_error = False

    def init(self):
        if not hasattr(self, 'panel'):
            self.window = sublime.active_window()
            self.panel = self.window.get_output_panel(self.name)
            self.panel.set_read_only(True)
            self.panel.settings().set('syntax', 'Packages/MavensMate/themes/MavensMate.hidden-tmLanguage')
            self.panel.settings().set('color_scheme', 'Packages/MavensMate/themes/MavensMate.hidden-tmTheme')
            self.panel.settings().set('word_wrap', True)
            self.panel.settings().set('gutter', True)
            self.panel.settings().set('line_numbers', True)

    def reset_hide(self):
        self.hide_time = None

    def show(self, force = False):
        self.init()
        settings = sublime.load_settings('mavensmate.sublime-settings')
        hide = settings.get('hide_output_panel', 1)
        if force or hide != True or not isinstance(hide, bool):
            self.visible = True
            self.window.run_command('show_panel', {'panel': 'output.' + self.name})

    def prepare_string(self, string, key, writeln=False):
        if len(string):
            try:
                if not isinstance(string, unicode):
                    string = unicode(string, 'UTF-8', errors='strict')
            except:
                if type(string) is not str:
                    string = str(string, 'utf-8')
            if os.name != 'nt':
                string = unicodedata.normalize('NFC', string)
            if writeln:
                string = string+"\n"
            self.strings[key].append(string)

    def write(self, string, key = 'sublime_mm', finish = False):
        if not len(string) and not finish:
            return
        if key not in self.strings:
            self.strings[key] = []
            self.queue.append(key)
        
        self.prepare_string(string, key)
        
        if finish:
            self.strings[key].append(None)
        sublime.set_timeout(self.write_callback, 0)
        return key

    def writeln(self, string, key = 'sublime_mm', finish = False):
        if not len(string) and not finish:
            return
        if key not in self.strings:
            self.strings[key] = []
            self.queue.append(key)
        
        self.prepare_string(string, key, True)
        
        if finish:
            self.strings[key].append(None)
        sublime.set_timeout(self.write_callback, 0)
        return key

    def write_callback(self):
        if config.sublime_version >= 3000:
            found = False
            for key in self.strings.keys():
                if len(self.strings[key]):
                    found = True
            if not found:
                return
            string = self.strings[key].pop(0)
            self.panel.run_command('mavens_mate_output_text', {'text': string})
            
            size = self.panel.size()
            sublime.set_timeout(lambda : self.panel.show(size, True), 2)

            return
        else:
            found = False
            for key in self.strings.keys():
                if len(self.strings[key]):
                    found = True
            if not found:
                return
            read_only = self.panel.is_read_only()
            if read_only:
                self.panel.set_read_only(False)
            edit = self.panel.begin_edit()
            keys_to_erase = []
            for key in list(self.queue):
                while len(self.strings[key]):
                    string = self.strings[key].pop(0)
                    if string == None:
                        self.panel.erase_regions(key)
                        keys_to_erase.append(key)
                        continue
                    if key == 'sublime_mm':
                        point = self.panel.size()
                    else:
                        regions = self.panel.get_regions(key)
                        if not len(regions):
                            point = self.panel.size()
                        else:
                            region = regions[0]
                            point = region.b + 1
                    if point == 0 and string[0] == '\n':
                        string = string[1:]
                    self.panel.insert(edit, point, string)
                    if key != 'sublime_mm':
                        point = point + len(string) - 1
                        region = sublime.Region(point, point)
                        self.panel.add_regions(key, [region], '')
        
            for key in keys_to_erase:
                if key in self.strings:
                    del self.strings[key]
                try:
                    self.queue.remove(key)
                except ValueError:
                    pass
            
            self.panel.end_edit(edit)
            if read_only:
                self.panel.set_read_only(True)
            size = self.panel.size()
            sublime.set_timeout(lambda : self.panel.show(size, True), 2)

