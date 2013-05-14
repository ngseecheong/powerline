# vim:fileencoding=utf-8:noet

from __future__ import absolute_import

from powerline.bindings.vim import vim_get_func
from powerline import Powerline
from powerline.lib import mergedicts
from powerline.matcher import gen_matcher_getter
import vim
from itertools import count


vim_exists = vim_get_func('exists', rettype=int)
vim_getwinvar = vim_get_func('getwinvar')
vim_setwinvar = vim_get_func('setwinvar')


def _override_from(config, override_varname):
	if vim_exists(override_varname):
		# FIXME vim.eval has problem with numeric types, vim.bindeval may be 
		# absent (and requires converting values to python built-in types), 
		# vim.eval with typed call like the one I implemented in frawor is slow. 
		# Maybe eval(vime.eval('string({0})'.format(override_varname)))?
		overrides = vim.eval(override_varname)
		mergedicts(config, overrides)
	return config


WINDOW_STASUSLINE = '%!PowerlinePyeval(\'powerline.statusline({0})\')'


class VimPowerline(Powerline):
	def __init__(self):
		super(VimPowerline, self).__init__('vim')
		self.last_window_id = 1

	def add_local_theme(self, key, config):
		'''Add local themes at runtime (during vim session).

		:param str key:
			Matcher name (in format ``{matcher_module}.{module_attribute}`` or 
			``{module_attribute}`` if ``{matcher_module}`` is 
			``powerline.matchers.vim``). Function pointed by 
			``{module_attribute}`` should be hashable and accept a dictionary 
			with information about current buffer and return boolean value 
			indicating whether current window matched conditions. See also 
			:ref:`local_themes key description <config-ext-local_themes>`.

		:param dict config:
			:ref:`Theme <config-themes>` dictionary.

		:return:
			``True`` if theme was added successfully and ``False`` if theme with 
			the same matcher already exists.
		'''
		self.update_renderer()
		key = self.get_matcher(key)
		try:
			self.renderer.add_local_theme(key, {'config': config})
		except KeyError:
			return False
		else:
			return True

	def load_main_config(self):
		return _override_from(super(VimPowerline, self).load_main_config(), 'g:powerline_config_overrides')

	def load_theme_config(self, name):
		# Note: themes with non-[a-zA-Z0-9_] names are impossible to override 
		# (though as far as I know exists() won’t throw). Won’t fix, use proper 
		# theme names.
		return _override_from(super(VimPowerline, self).load_theme_config(name),
						'g:powerline_theme_overrides__' + name)

	def get_local_themes(self, local_themes):
		if not local_themes:
			return {}

		self.get_matcher = gen_matcher_getter(self.ext, self.import_paths)
		return dict(((self.get_matcher(key), {'config': self.load_theme_config(val)})
					for key, val in local_themes.items()))

	def get_config_paths(self):
		if vim_exists('g:powerline_config_path'):
			return [vim.eval('g:powerline_config_path')]
		else:
			return super(VimPowerline, self).get_config_paths()

	@staticmethod
	def get_segment_info():
		return {}

	def reset_highlight(self):
		try:
			self.renderer.reset_highlight()
		except AttributeError:
			# Renderer object appears only after first `.render()` call. Thus if 
			# ColorScheme event happens before statusline is drawn for the first 
			# time AttributeError will be thrown for the self.renderer. It is 
			# fine to ignore it: no renderer == no colors to reset == no need to 
			# do anything.
			pass

	if all((hasattr(vim.current.window, attr) for attr in ('options', 'vars', 'number'))):
		def win_idx(self, window_id):
			r = None
			for window in vim.windows:
				try:
					curwindow_id = window.vars['powerline_window_id']
				except KeyError:
					curwindow_id = self.last_window_id
					self.last_window_id += 1
					window.vars['powerline_window_id'] = curwindow_id
				statusline = WINDOW_STASUSLINE.format(curwindow_id)
				if window.options['statusline'] != statusline:
					window.options['statusline'] = statusline
				if curwindow_id == window_id if window_id else window is vim.current.window:
					assert r is None, "Non-unique window ID"
					r = (window, curwindow_id, window.number)
			return r
	else:
		def win_idx(self, window_id):  # NOQA
			r = None
			for winnr, window in zip(count(1), vim.windows):
				curwindow_id = vim_getwinvar(winnr, 'powerline_window_id')
				if curwindow_id:
					curwindow_id = int(curwindow_id)
				else:
					curwindow_id = self.last_window_id
					self.last_window_id += 1
					vim_setwinvar(winnr, 'powerline_window_id', curwindow_id)
				statusline = WINDOW_STASUSLINE.format(curwindow_id)
				if vim_getwinvar(winnr, '&statusline') != statusline:
					vim_setwinvar(winnr, '&statusline', statusline)
				if curwindow_id == window_id if window_id else window is vim.current.window:
					assert r is None, "Non-unique window ID"
					r = (window, curwindow_id, winnr)
			return r

	def statusline(self, window_id):
		window, window_id, winnr = self.win_idx(window_id) or (None, None, None)
		if not window:
			return 'No window {0}'.format(window_id)
		return self.render(window, window_id, winnr)

	def new_window(self):
		window, window_id, winnr = self.win_idx(None)
		return self.render(window, window_id, winnr)
