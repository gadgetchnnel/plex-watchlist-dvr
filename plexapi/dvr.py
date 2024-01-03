# -*- coding: utf-8 -*-
from urllib.parse import urlencode, quote_plus

from plexapi.base import OPERATORS, PlexObject
from plexapi.exceptions import BadRequest, NotFound
from plexapi.library import LibrarySection, FilteringType, FilteringFieldType
from plexapi.settings import Setting
from plexapi import utils, X_PLEX_CONTAINER_SIZE


class MediaProvider(PlexObject):
    TAG = 'MediaProvider'

    def _loadData(self, data):
        """ Load attribute values from Plex XML response. """
        self._data = data
        self.identifier = data.attrib.get('identifier')
        self.id = data.attrib.get('id')
        self.parentId = data.attrib.get('parentID')
        self.protocols = data.attrib.get('protocols')


class MediaSubscription(PlexObject):
    TAG = 'MediaSubscription'

    def _loadData(self, data):
        self._data = data
        self.key = data.attrib.get("key")
        self.type = data.attrib.get("type")
        self.targetLibrarySectionID = data.attrib.get("targetLibrarySectionID")
        self.targetSectionLocationID = data.attrib.get("targetLibrarySectionLocationID")
        self.createdAt = utils.toDatetime(data.attrib.get("createdAt"))
        self.title = data.attrib.get("title")
        self.airingsType = data.attrib.get("airingsType")
        self.librarySectionTitle = data.attrib.get("librarySectionTitle")
        self.locationPath = data.attrib.get("locationPath")
        self.item = self.findItem(data)


class PlexDvr(PlexObject):
    key = '/livetv/dvrs'
    TAG = 'Dvr'

    def _loadData(self, data):
        """ Load attribute values from Plex XML response. """
        self._data = data
        self.epgIdentifier = data.find('Dvr').attrib.get('epgIdentifier')
        self.dvrKey = data.find('Dvr').attrib.get('key')
        providerData = self._server.query("/media/providers")
        self.mediaProviders = self._server.findItems(providerData, MediaProvider, initpath='/' + self.epgIdentifier)

    def sections(self):
        data = self._server.query("/%s/sections" % self.epgIdentifier)
        return self._server.findItems(data, DvrSection, initpath='/' + self.epgIdentifier)

    def section(self, section_name):
        data = self._server.query("/%s/sections" % self.epgIdentifier)
        sections = self._server.findItems(data, DvrSection, initpath='/' + self.epgIdentifier)
        return next(s for s in sections if s.title == section_name)

    def settings(self):
        """ Returns a list of all library settings. """
        key = '/livetv/dvrs/%s/' % self.dvrKey
        data = self._server.query(key)
        return self.findItems(data, cls=Setting, rtag='Dvr', etag='Setting')

    def _getSetting(self, settings, id, default):
        setting = next((s for s in settings if s.id == id), None)
        return setting.value if setting else default

    def subscriptions(self):
        key = "/media/subscriptions"
        data = self._server.query(key)
        return self.findItems(data, cls=MediaSubscription)

    def submitRecording(self, item, thumb=None, **kwargs):
        """ Edit a library's advanced settings. """
        data = {}
        idEnums = {}
        hintKey = 'hints[%s]'
        paramKey = 'params[%s]'
        prefKey = 'prefs[%s]'

        settings = self.settings()

        prefs = {
            "minVideoQuality": 0,
            "replaceLowerQuality": False,
            "recordPartials": False,
            "startOffsetMinutes": 0,
            "endOffsetMinutes": 0,
            "lineupChannel": "",
            "startTimeslot": -1,
            "comskipEnabled": -1,
            "comskipMethod": 2,
            "oneShot": True,
            "remoteMedia": False
        }

        for prefName in prefs.keys():
            value = self._getSetting(settings, prefName, prefs[prefName])
            if isinstance(value, bool):
                value = "true" if value else "false"
            data[prefKey % prefName] = value

        for setting in self.settings():
            if setting.type != 'bool':
                idEnums[setting.id] = setting.enumValues
            else:
                idEnums[setting.id] = {0: False, 1: True}

        data[hintKey % "title"] = item.title
        data[hintKey % "year"] = item.year
        if item.ratingKey != item.ratingKey:
            data[hintKey % "ratingKey"] = quote_plus(item.guid)
        else:
            data[hintKey % "ratingKey"] = item.ratingKey
        data[hintKey % "guid"] = item.guid
        data[hintKey % "type"] = "1" if item.type == "movie" else "2"
        data[hintKey % "thumb"] = thumb if thumb else item.thumb

        data[paramKey % "libraryType"] = "1" if item.type == "movie" else "2"
        provider = next((p for p in self.mediaProviders
                         if p.parentId == self.dvrKey and p.protocols == "livetv"), None)
        data[paramKey % "mediaProviderID"] = provider.id

        data["targetLibrarySectionID"] = "70"
        data["type"] = "1" if item.type == "movie" else "2"

        for settingID, value in kwargs.items():
            try:
                enums = idEnums[settingID]
            except KeyError:
                raise NotFound('%s not found in %s' % (value, list(idEnums.keys())))
            if enums is None or value in enums:
                data[prefKey % settingID] = value
            else:
                raise NotFound('%s not found in %s' % (value, enums))

        self.edit(**data)

    def edit(self, agent=None, **kwargs):
        """ Edit a library. See :class:`~plexapi.library.Library` for example usage.

            Parameters:
                agent (str, optional): The library agent.
                kwargs (dict): Dict of settings to edit.
        """
        params = list(kwargs.items())

        part = '/media/subscriptions?%s' % urlencode(params, doseq=True)
        self._server.query(part, method=self._server._session.post)


class DvrSection(LibrarySection):
    def _loadFilters(self):
        """ Retrieves and caches the list of :class:`~plexapi.library.FilteringType` and
            list of :class:`~plexapi.library.FilteringFieldType` for this library section.
        """
        _key = ('%s/sections/%s/%s?includeMeta=1&includeAdvanced=1'
                '&X-Plex-Container-Start=0&X-Plex-Container-Size=0')

        key = _key % (self._initpath, self.key, 'all')
        data = self._server.query(key)
        self._filterTypes = self.findItems(data, FilteringType, rtag='Meta')
        self._fieldTypes = self.findItems(data, FilteringFieldType, rtag='Meta')

    def _buildSearchKey(self, title=None, sort=None, libtype=None, limit=None, filters=None, returnKwargs=False,
                        **kwargs):
        """ Returns the validated and formatted search query API key
            (``/library/sections/<sectionKey>/all?<params>``).
        """
        args = {}
        filter_args = []

        args['includeGuids'] = int(bool(kwargs.pop('includeGuids', True)))
        for field, values in list(kwargs.items()):
            if field.split('__')[-1] not in OPERATORS:
                filter_args.append(self._validateFilterField(field, values, libtype))
                del kwargs[field]
        if title is not None:
            if isinstance(title, (list, tuple)):
                filter_args.append(self._validateFilterField('title', title, libtype))
            else:
                args['title'] = title
        if filters is not None:
            filter_args.extend(self._validateAdvancedSearch(filters, libtype))
        if sort is not None:
            args['sort'] = self._validateSortFields(sort, libtype)
        if libtype is not None:
            args['type'] = utils.searchType(libtype)
        if limit is not None:
            args['limit'] = limit

        joined_args = utils.joinArgs(args).lstrip('?')
        joined_filter_args = '&'.join(filter_args) if filter_args else ''
        params = '&'.join([joined_args, joined_filter_args]).strip('&')
        key = '%s/sections/%s/all?%s' % (self._initpath, self.key, params)

        if returnKwargs:
            return key, kwargs
        return key

    def search(self, title=None, sort=None, maxresults=None, libtype=None,
               container_start=0, container_size=X_PLEX_CONTAINER_SIZE, limit=None, filters=None, **kwargs):
        key, kwargs = self._buildSearchKey(
            title=title, sort=sort, libtype=libtype, limit=limit, filters=filters, returnKwargs=True, **kwargs)
        return self._search(key, maxresults, container_start, container_size, **kwargs)
