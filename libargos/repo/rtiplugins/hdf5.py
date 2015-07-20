# -*- coding: utf-8 -*-

# This file is part of Argos.
# 
# Argos is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Argos is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Argos. If not, see <http://www.gnu.org/licenses/>.

""" Repository Tree Items (RTIs) for HDF-5 data.

    It uses the h5py package to open HDF-5 files.
    See http://www.h5py.org/
"""

import logging, os
import h5py

from libargos.qt import QtGui
from libargos.utils.cls import check_class
from libargos.repo.baserti import (ICONS_DIRECTORY, BaseRti)

logger = logging.getLogger(__name__)



class H5pyFieldRti(BaseRti):
    """ Repository Tree Item (RTI) that contains a field in a compound HDF-5 variable. 
    """ 
    _iconOpen = QtGui.QIcon(os.path.join(ICONS_DIRECTORY, 'h5py.field.svg'))
    _iconClosed = _iconOpen 
    
    def __init__(self, h5Dataset, nodeName, fileName=''):
        """ Constructor.
            The name of the field must be given to the nodeName parameter. 
        """
        super(H5pyFieldRti, self).__init__(nodeName, fileName=fileName)
        check_class(h5Dataset, h5py.Dataset)
        self._h5Dataset = h5Dataset

    def hasChildren(self):
        """ Returns False. Field nodes never have children. 
        """
        return False
   
    @property
    def attributes(self):
        """ The attributes dictionary. 
            Returns the attributes of the variable that contains this field.
        """        
        return self._h5Dataset.attrs
    
    @property
    def _asArray(self):
        """ Returns the HDf-5 dataset this field belongs to
            The return type is a h5py.Dataset, not a numpy array!
        """
        return self._h5Dataset
    
    
    def __getitem__(self, index):
        """ Called when using the RTI with an index (e.g. rti[0]).
            Applies the index on the HDF5 dataset that contain this field and then selects the
            current field. In pseudo-code, it returns: self.dataset[index][self.nodeName].
        """
        slicedArray = self._asArray.__getitem__(index)
        fieldName = self.nodeName
        return slicedArray[fieldName]

    
    @property
    def elementTypeName(self):
        """ String representation of the element type.
        """
        fieldName = self.nodeName
        return str(self._h5Dataset.dtype.fields[fieldName][0])
    
    

class H5pyDatasetRti(BaseRti):
    """ Repository Tree Item (RTI) that contains a HDF5 dataset. 
    """ 
    _iconOpen = QtGui.QIcon(os.path.join(ICONS_DIRECTORY, 'h5py.variable.svg'))
    _iconClosed = _iconOpen 
    
    def __init__(self, h5Dataset, nodeName, fileName=''):
        """ Constructor
        """
        super(H5pyDatasetRti, self).__init__(nodeName, fileName=fileName)
        check_class(h5Dataset, h5py.Dataset)
        self._h5Dataset = h5Dataset
        self._isCompound = bool(self._h5Dataset.dtype.names)

            
    def hasChildren(self):
        """ Returns True if the variable has a compound type, otherwise returns False.
        """
        return self._isCompound

   
    @property
    def attributes(self):
        """ The attributes dictionary.
        """        
        return self._h5Dataset.attrs
    

    @property
    def _asArray(self):
        """ Returns the the underlying HDF-5 dataset.
            The return type is a h5py.Dataset, not a numpy array!
        """        
        return self._h5Dataset
    
    @property
    def elementTypeName(self):
        """ String representation of the element type.
        """        
        dtype =  self._h5Dataset.dtype 
        return '<compound>' if dtype.names else str(dtype)
    
               
    @property
    def dimensionNames(self):
        """ Returns a list with the dimension names of the underlying HDF-5 dataset.
        
            First looks in the dataset's dimension scales to see if it refers to another
            dataset. In that case the referred dataset's name is used. If not, the label of the
            dimension scale is used. Finally, if this is empty, the dimension is numbered.
        """
        dimNames = [] # TODO: cache?
        for dimNr, dimScales in enumerate(self._h5Dataset.dims):
            if len(dimScales) == 0:
                dimNames.append('Dim{}'.format(dimNr))
            elif len(dimScales) == 1:
                dimScaleLabel, dimScaleDataset = dimScales.items()[0]
                path = dimScaleDataset.name
                if path:
                    dimNames.append(os.path.basename(path))
                elif dimScaleLabel: # This could potentially be long so it's our second choice 
                    dimNames.append(dimScaleLabel)
                else:
                    dimNames.append('Dim{}'.format(dimNr))
            else:
                # TODO: multiple scales for this dimension. What to do?
                logger.warn("More than one dimension scale found: {!r}".format(dimScales))
                dimNames.append('Dim{}'.format(dimNr)) # For now, just number them
                                 
        return dimNames
    
                   
    def _fetchAllChildren(self):
        """ Fetches all fields that this variable contains. 
            Only variables with a compound data type can have fields.
        """        
        assert self.canFetchChildren(), "canFetchChildren must be True"

        childItems = []

        # Add fields
        if self._isCompound:
            for fieldName in self._h5Dataset.dtype.names:
                childItems.append(H5pyFieldRti(self._h5Dataset, nodeName=fieldName, 
                                               fileName=self.fileName))
                        
        self._childrenFetched = True
        return childItems
    
    
class H5pyGroupRti(BaseRti):
    """ Repository Tree Item (RTI) that contains a HDF-5 group. 
    """     
    _iconClosed = QtGui.QIcon(os.path.join(ICONS_DIRECTORY, 'h5py.group-closed.svg'))
    _iconOpen = QtGui.QIcon(os.path.join(ICONS_DIRECTORY, 'h5py.group-open.svg'))
    
    def __init__(self, h5Group, nodeName, fileName=''):
        """ Constructor
        """
        super(H5pyGroupRti, self).__init__(nodeName, fileName=fileName)
        check_class(h5Group, h5py.Group, allow_none=True)

        self._h5Group = h5Group
        self._childrenFetched = False
        
    @property
    def attributes(self):
        """ The attributes dictionary.
        """
        return self._h5Group.attrs if self._h5Group else {}
        
               
    def _fetchAllChildren(self):
        """ Fetches all sub groups and variables that this group contains.
        """
        assert self._h5Group is not None, "dataset undefined (file not opened?)"
        assert self.canFetchChildren(), "canFetchChildren must be True"
        
        childItems = []

        for childName, h5Child in self._h5Group.items():
            if isinstance(h5Child, h5py.Group):
                childItems.append(H5pyGroupRti(h5Child, nodeName=childName, 
                                               fileName=self.fileName))
            elif isinstance(h5Child, h5py.Dataset):
                childItems.append(H5pyDatasetRti(h5Child, nodeName=childName, 
                                                 fileName=self.fileName))
            else:
                logger.warn("Unexpected HDF-5 type (ignored): {}".format(type(h5Child)))
                        
        self._childrenFetched = True
        return childItems
    


class H5pyFileRti(H5pyGroupRti):
    """ Repository tree item that contains a netCDF file.
    """
    _iconClosed = QtGui.QIcon(os.path.join(ICONS_DIRECTORY, 'h5py.file-closed.svg'))
    _iconOpen = QtGui.QIcon(os.path.join(ICONS_DIRECTORY, 'h5py.file-open.svg'))
        
    def __init__(self, nodeName, fileName=''):
        """ Constructor
        """
        super(H5pyFileRti, self).__init__(None, nodeName, fileName=fileName)
        self._checkFileExists()
    
    def _openResources(self):
        """ Opens the root Dataset.
        """
        logger.info("Opening: {}".format(self._fileName))
        self._h5Group = h5py.File(self._fileName, 'r')

    
    def _closeResources(self):
        """ Closes the root Dataset.
        """
        logger.info("Closing: {}".format(self._fileName))
        self._h5Group.close()
        self._h5Group = None