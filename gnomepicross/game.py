#!/usr/bin/env python
#
# Copyright (C) 2007 Sascha Peilicke <sasch.pe@gmx.de>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA
#

from random import randrange
from zipfile import ZipFile
from StringIO import StringIO

from timer import PeriodicTimer



# Constants
DEFAULT_LEVELPACK = './data/default_pack.zip'
DEFAULT_PLAYTIME = 1800
DEFAULT_TIME_PENALTY = 120
DEFAULT_TIME_PENALTY_CAP = 480

SKILL_EASY = 'Easy'			# These values should match the
SKILL_MEDIUM = 'Medium'		# the level files!
SKILL_HARD = 'Hard'

FIELD_INVALID = 0			# Constants describing a field on 
FIELD_VALID = 1				# the playfield
FIELD_MARKED_VALID = 2
FIELD_MARKED_INVALID = 4
FIELD_OPEN = 8



class Game(object):
	"""A paint by numbers game also called nonogram.
	"""
	
	def __init__(self,playTime=DEFAULT_PLAYTIME,timePenalty=DEFAULT_TIME_PENALTY,skill=None):
		"""Creates a picross game.

		Parameters:
			playTime	- Time to play (in seconds)
			timePenalty	- Applied when the user opens a wrong field
			skill		- Desired skill level (None == random)
		"""
		self.__level = None
		self.__name = None
		self.__skill = None
		self.__gameOver = False
		self.__playTime = self.__timeLeft = playTime
		self.__timePenalty = timePenalty
		self.__currentTimePenalty = self.__timePenalty
		self.__fieldsToOpen = 0
		self.__fieldsOpened = 0
		self.__isPaused = False

		self.load(skill=skill)

		self.__timer = PeriodicTimer(delay=1,interval=1,callback=self.__timerCallback)
		self.__timer.start()

	#
	# Miscellaneous methods
	#

	def __timerCallback(self):
		"""Called by the timer every second.
		"""
		if self.__timeLeft <= 0:
			self.__timer.cancel()
			self.__gameOver = True
		else:
			if self.__fieldsOpened == self.__fieldsToOpen:
				self.__timer.cancel()
			else:
				self.__timeLeft -= 1


	def _debug_print(self):
		print self.getInfo()
		print 'go: %s time: %s' % (self.__gameOver,self.__timeLeft)
		for row in self.__level:
			print row


	#
	# Game information retrieval
	#

	def getInfo(self):
		"""Returns the name, skill and size of the level
		"""
		return self.__name,self.__skill,len(self.__level)


	def getRowHint(self,row):
		"""Returns the hint for a specific row.
		"""
		hint,count = [],0
		for columnItem in self.__level[row]:
			if columnItem == FIELD_VALID:
				count += 1
			else:
				if count > 0:
					hint.append(count)
					count = 0
		if count > 0:
			hint.append(count)
		if not hint:
			hint.append(0)	
		return hint


	def getColumnHint(self,col):
		"""Returns the hint for a specific column.
		"""
		hint,count = [],0
		for row in self.__level:
			if row[col] == FIELD_VALID:
				count += 1
			else:
				if count > 0:
					hint.append(count)
					count = 0
		if count > 0:
			hint.append(count)
		if not hint: 
			hint.append(0)
		return hint


	def getTimes(self):
		"""Returns the time left and the overall time
		"""
		return self.__timeLeft,self.__playTime


	def getField(self,col,row):
		return self.__level[row][col]


	def isGameOver(self):
		return self.__gameOver


	def isPaused(self):
		return self.__isPaused


	def isGameWon(self):
		return (not self.__timer.isAlive()) and (not self.__gameOver)


	#
	# Game manipulation methods
	#

	def restart(self):
		"""Reinitializes the current game 
		"""
		for row in self.__level:
			for field in row:
				if field == FIELD_OPEN or field == FIELD_MARKED_VALID:
					self.__level[row][field] = FIELD_VALID
				elif field == FIELD_MARKED_INVALID:
					self.__level[row][field] = FIELD_INVALID
		self.__gameOver = False
		self.__currentTimePenalty = self.__timePenalty
		self.__timeLeft = self.__playTime
		self.__fieldsOpened = 0


	def pause(self):
		if not self.__gameOver and not self.isGameWon:
			self.__timer.pause()
			self.__isPaused = not self.__isPaused
			return True
		else:
			return False


	def openField(self,col,row):
		field = self.__level[row][col]
		if field == FIELD_VALID or field == FIELD_MARKED_VALID:
			self.__level[row][col] = FIELD_OPEN
			self.__fieldsOpened += 1
			return True
		else:
			self.__timeLeft -= self.__currentTimePenalty
			self.__currentTimePenalty += self.__timePenalty
			if self.__currentTimePenalty > DEFAULT_TIME_PENALTY_CAP:
				self.__currentTimePenalty = DEFAULT_TIME_PENALTY_CAP
			if self.__timeLeft < 0: 
				self.__timeLeft = 0
			return False


	def markField(self,col,row):
		field = self.__level[row][col]
		if field == FIELD_VALID:
			self.__level[row][col] = FIELD_MARKED_VALID
		elif field == FIELD_MARKED_VALID:
			self.__level[row][col] = FIELD_VALID
		elif field == FIELD_INVALID:
			self.__level[row][col] = FIELD_MARKED_INVALID
		elif field == FIELD_MARKED_INVALID:
			self.__level[row][col] = FIELD_INVALID
		return self.__level[row][col]
	

	def load(self,file=DEFAULT_LEVELPACK,skill=None):
		"""Loads a level either from a zipped levelpack or from a textfile.

		Parameters:
			file	- Can be a file path or zipped levelpack
			skill	- Desired level skill (None == random)
		"""
		if file.endswith('.lvl'):
			# Set the skill variable
			if file.startswith('easy'):		self.__skill = SKILL_EASY
			elif file.startswith('medium'):	self.__skill = SKILL_MEDIUM
			elif file.startswith('hard'):	self.__skill = SKILL_HARD

			self.__loadFileContent(open(file,'r'))

		elif file.endswith('.zip'):
			zip = ZipFile(file)

			# We have to select from which files in the zipfile we 
			# want to choose randomly based on the level's skill
			candidates = []

			if skill == SKILL_EASY:
				for file in zip.namelist():
					if file.startswith('easy'):
						candidates.append(file)				
			elif skill == SKILL_MEDIUM:
				for file in zip.namelist():
					if file.startswith('medium'):
						candidates.append(file)				
			elif skill == SKILL_HARD:
				for file in zip.namelist():
					if file.startswith('hard'):
						candidates.append(file)				

			# This should never happen in a good levelpack, but if it
			# is malformed, just pick something!
			if not candidates:
				candidates = zip.namelist()

			# Select one candidate randomly
			which = candidates[randrange(len(candidates))]
			# Set the skill variable
			if which.startswith('easy'):	self.__skill = SKILL_EASY
			elif which.startswith('medium'):self.__skill = SKILL_MEDIUM
			elif which.startswith('hard'):	self.__skill = SKILL_HARD
			# Read from zipfile and load file content
			buf = zip.read(which)
			self.__loadFileContent(StringIO(buf))


	def __loadFileContent(self,file):
		"""Actually loads the level data from a file.
		"""
		self.__level = []
		for line in file:
			if line.startswith('name:'):
				self.__name = line[5:].strip()
			elif line[0] == '0' or line[0] == '1':
				row = []
				for field in line:
					if field == '0': 
						row.append(FIELD_INVALID)
					elif field == '1':
						self.__fieldsToOpen += 1
						row.append(FIELD_VALID)
				self.__level.append(row)
