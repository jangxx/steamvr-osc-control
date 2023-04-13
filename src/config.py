import json
import os

from appdirs import user_config_dir

CONFIG_DIR = user_config_dir("SteamVR OSC Control", "jangxx")

def merge_config_dicts(base_config, merge_src):
	result = {}
	for key in merge_src:
		if key in base_config:
			if isinstance(base_config[key], dict) and isinstance(merge_src[key], dict):
				result[key] = merge_config_dicts(base_config[key], merge_src[key])
			elif not isinstance(base_config[key], dict) and not isinstance(merge_src[key], dict):
				result[key] = merge_src[key]
			else: # objects are of different types (one is dict, the other isn't)
				result[key] = base_config[key] # just use the base config in that case
		else:
			result[key] = merge_src[key]

	for key in base_config:
		if not key in result:
			result[key] = base_config[key]

	return result

class Config:
	def __init__(self):
		self._config_path = os.path.join(CONFIG_DIR, "config.json")

		self._config = {
			"osc": {
				"listen_address": "127.0.0.1",
				"listen_port": 9001,
			},
			"screenshots": {
				"save_path": "SteamVR",
				"relative_to_pictures": True
			},
			"command_mapping": {}
		}

		self.reload()

	def reload(self):
		if os.path.exists(self._config_path):
			with open(self._config_path, "r") as configfile:
				file_config = json.load(configfile)
				self._config = merge_config_dicts(self._config, file_config)

	def save(self):
		with open(self._config_path, "w+") as configfile:
			json.dump(self._config, configfile, indent=4)

	def get(self, path):
		ret = self._config

		if not type(path) is list:
			path = [ path ]

		for e in path:
			ret = ret[e]

		return ret

	def set(self, path, value):
		elem = self._config
		
		for e in path[:-1]:
			elem = elem[e]

		elem[path[-1]] = value

		self.save()

	def delete(self, path):
		elem = self._config
		
		for e in path[:-1]:
			elem = elem[e]

		del elem[path[-1]]

		self.save()

	def delete_safe(self, path):
		if self.exists(path):
			self.delete(path)
			return True
		else:
			return False

	def exists(self, path):
		cur = self._config

		if not type(path) is list:
			path = [ path ]

		for e in path:
			if not e in cur:
				return False
			else:
				cur = cur[e]

		return True

		