# Third-Party Notices

Unless a file or directory states otherwise, project-owned CO-Calib code,
documentation, and detector weights are licensed under the top-level
BSD-4-Clause `LICENSE`.

`vendor/kalibr` contains a modified copy of ETH Zurich / ASL Kalibr and its
bundled components. The original copyright and redistribution terms are
retained in `vendor/kalibr/LICENSE`. Redistributions must retain its copyright
notices, conditions, disclaimer, advertising acknowledgement, and
non-endorsement clause.

The following bundled Kalibr components declare LGPLv3 terms:

- `vendor/kalibr/aslam_incremental_calibration/incremental_calibration`
- `vendor/kalibr/aslam_incremental_calibration/incremental_calibration_python`

Copies of LGPLv3 and GPLv3 are provided in `LICENSES/`. Modifications to these
components remain governed by LGPLv3. Binary and container redistributions must
also satisfy the LGPLv3 requirements applicable to combined works.

Python runtime dependencies remain separate packages and are installed from their normal distribution channels by `environment.yml`.
