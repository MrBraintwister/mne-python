# -*- coding: utf-8 -*-
"""Test the compute_current_source_density function.

For each supported file format, implement a test.
"""
# Authors: Alex Rockhill <aprockhill@mailbox.org>
#
# License: BSD (3-clause)

import os.path as op

import numpy as np

import pytest
from numpy.testing import assert_allclose

from mne.channels import make_dig_montage
from mne import create_info, EpochsArray, pick_types
from mne.io import read_raw_fif
from mne.io.constants import FIFF
from mne.utils import object_diff, run_tests_if_main
from mne.datasets import testing

from mne.preprocessing import compute_current_source_density


eeg_fname = './data/test_eeg.csv'
coords_fname = './data/test_eeg_pos.csv'
csd_fname = './data/test_eeg_csd.csv'

ch_names = ['Fp1', 'AF7', 'AF3', 'F1', 'F3', 'F5', 'F7', 'FT7', 'FC5',
            'FC3', 'FC1', 'C1', 'C3', 'C5', 'T7', 'TP7', 'CP5', 'CP3',
            'CP1', 'P1', 'P3', 'P5', 'P7', 'P9', 'PO7', 'PO3', 'O1',
            'Iz', 'Oz', 'POz', 'Pz', 'CPz', 'Fpz', 'Fp2', 'AF8', 'AF4',
            'AFz', 'Fz', 'F2', 'F4', 'F6', 'F8', 'FT8', 'FC6', 'FC4',
            'FC2', 'FCz', 'Cz', 'C2', 'C4', 'C6', 'T8', 'TP8', 'CP6',
            'CP4', 'CP2', 'P2', 'P4', 'P6', 'P8', 'P10', 'PO8', 'PO4',
            'O2']

io_path = op.join(op.dirname(__file__), '..', '..', 'io', 'tests', 'data')
raw_fname = op.join(io_path, 'test_raw.fif')


@pytest.fixture(scope='function', params=[testing._pytest_param()])
def epochs_csd_sphere():
    """Get the MATLAB EEG data."""
    data = np.genfromtxt(eeg_fname, delimiter=',')
    # re-arrange data into a 3d array
    data = data.reshape((64, 640, 99), order='F')
    # swap data's shape
    data = np.rollaxis(data, 2)
    # re-scale data
    data *= 1e-6
    coords = np.genfromtxt(coords_fname, delimiter=',')
    csd = np.genfromtxt(csd_fname, delimiter=',')

    sphere = (0, 0, 0, 85)
    sfreq = 256  # sampling rate
    # swap coordinates' shape
    pos = np.rollaxis(coords, 1)
    # swap coordinates' positions
    pos[:, [0]], pos[:, [1]] = pos[:, [1]], pos[:, [0]]
    # invert first coordinate
    pos[:, [0]] *= -1
    # assign channel names to coordinates
    dig_ch_pos = dict(zip(ch_names, pos))
    montage = make_dig_montage(ch_pos=dig_ch_pos, nasion=(0, 50, 0),
                               lpa=(-100, 0, 0), rpa=(100, 0, 0))
    # create info
    info = create_info(ch_names=ch_names, sfreq=sfreq, ch_types='eeg')
    # make Epochs object
    epochs = EpochsArray(data=data, info=info, tmin=-1)
    epochs.set_montage(montage)
    return epochs, csd, sphere


def test_csd_matlab(epochs_csd_sphere):
    """Test replication of the CSD MATLAB toolbox."""
    epochs, csd, sphere = epochs_csd_sphere
    epochs_csd = compute_current_source_density(epochs,
                                                sphere=sphere)
    print(epochs_csd.average().data)
    print(csd)
    assert_allclose(epochs_csd.average().data, csd, atol=1e-4)

    # test raw
    csd_epochs = compute_current_source_density(epochs, sphere=sphere)

    with pytest.raises(ValueError, match=('CSD already applied, '
                                          'should not be reapplied')):
        compute_current_source_density(csd_epochs, sphere=sphere)

    assert_allclose(csd_epochs._data.sum(), 0.0001411335742733275, atol=1e-3)

    csd_evoked = compute_current_source_density(epochs.average(),
                                                sphere=sphere)
    assert_allclose(csd_evoked.data, csd_epochs._data.mean(0), atol=1e-3)


def test_csd_degenerate(epochs_csd_sphere):
    """Test degenerate conditions."""
    epochs, csd, sphere = epochs_csd_sphere
    warn_epochs = epochs.copy()
    warn_epochs.info['bads'].append(warn_epochs.ch_names[3])
    with pytest.raises(ValueError, match='Either drop.*or interpolate'):
        compute_current_source_density(warn_epochs)

    with pytest.raises(TypeError, match='must be an instance of'):
        compute_current_source_density(None)

    fail_epochs = epochs.copy()
    with pytest.raises(ValueError, match='Zero or infinite position'):
        for ch in fail_epochs.info['chs']:
            ch['loc'][:3] = np.array([0, 0, 0])
        compute_current_source_density(fail_epochs, sphere=sphere)

    with pytest.raises(ValueError, match='Zero or infinite position'):
        fail_epochs.info['chs'][3]['loc'][:3] = np.inf
        compute_current_source_density(fail_epochs, sphere=sphere)

    with pytest.raises(ValueError, match=('No EEG channels found.')):
        fail_epochs = epochs.copy()
        fail_epochs.set_channel_types({ch_name: 'ecog' for ch_name in
                                       fail_epochs.ch_names})
        compute_current_source_density(fail_epochs, sphere=sphere)

    with pytest.raises(TypeError):
        compute_current_source_density(epochs, lambda2='0', sphere=sphere)

    with pytest.raises(ValueError, match='lambda2 must be between 0 and 1'):
        compute_current_source_density(epochs, lambda2=2, sphere=sphere)

    with pytest.raises(TypeError):
        compute_current_source_density(epochs, stiffness='0', sphere=sphere)

    with pytest.raises(ValueError, match='stiffness must be non-negative'):
        compute_current_source_density(epochs, stiffness=-2, sphere=sphere)

    with pytest.raises(TypeError):
        compute_current_source_density(epochs, n_legendre_terms=0.1,
                                       sphere=sphere)

    with pytest.raises(ValueError, match=('n_legendre_terms must be '
                                          'greater than 0')):
        compute_current_source_density(epochs, n_legendre_terms=0,
                                       sphere=sphere)

    with pytest.raises(TypeError):
        compute_current_source_density(epochs, sphere=-0.1)

    with pytest.raises(ValueError, match=('sphere radius must be '
                                          'greater than 0')):
        compute_current_source_density(epochs, sphere=(-0.1, 0., 0., -1.))

    with pytest.raises(TypeError):
        compute_current_source_density(epochs, copy=2, sphere=sphere)


def test_csd_fif():
    """Test applying CSD to FIF data."""
    raw = read_raw_fif(raw_fname).load_data()
    raw.info['bads'] = []
    picks = pick_types(raw.info, meg=False, eeg=True)
    assert 'csd' not in raw
    orig_eeg = raw.get_data('eeg')
    assert len(orig_eeg) == 60
    raw_csd = compute_current_source_density(raw)
    assert 'eeg' not in raw_csd
    new_eeg = raw_csd.get_data('csd')
    assert not (orig_eeg == new_eeg).any()

    # reset the only things that should change, and assert objects are the same
    assert raw_csd.info['custom_ref_applied'] == FIFF.FIFFV_MNE_CUSTOM_REF_CSD
    raw_csd.info['custom_ref_applied'] = 0
    for pick in picks:
        ch = raw_csd.info['chs'][pick]
        assert ch['coil_type'] == FIFF.FIFFV_COIL_EEG_CSD
        assert ch['unit'] == FIFF.FIFF_UNIT_V_M2
        ch.update(coil_type=FIFF.FIFFV_COIL_EEG, unit=FIFF.FIFF_UNIT_V)
        raw_csd._data[pick] = raw._data[pick]
    assert object_diff(raw.info, raw_csd.info) == ''


run_tests_if_main()
