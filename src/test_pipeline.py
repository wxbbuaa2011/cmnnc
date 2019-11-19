# Copyright (c) 2019, IBM Research.
#
# Author: Kornilios Kourtis <kou@zurich.ibm.com>
#
# vim: set expandtab softtabstop=4 tabstop=4 shiftwidth=4:

from pprint import pprint
import numpy as np

import pipeline as pl
import conv


def test_mxv():
    params = {'n': 128 }

    # read access relation (vector x)
    rd_a = "{{ S[i] -> x[j] : i = 0 and 0 <= j < {n} }}".format(**params)
    # write access relation (vector y)
    wr_a = "{{ S[i] -> y[j] : i = 0 and 0 <= j < {n} }}".format(**params)
    # Define a stage based on the above relations
    stage = pl.Stage(pl.StageInfo(
        rd_a = rd_a,
        wr_a = wr_a,
    ))

    # Objects
    objs = {
        'x': (params['n'], ),
        'y': (params['n'], )
    }

    # Initialize matrix, and create core configuration
    # np.random.seed(666)
    m_shape = eval("(n,n)", params)
    m = np.random.rand(*m_shape)
    cconf = pl.CoreConf(m)

    # Initalize pipeline
    pline = pl.Pipeline([stage], objs, execute_ops=True)
    x = pline.get_object("x")
    x[...] = np.random.rand(params['n'])

    # Configure pipeline
    pline.configure([cconf])

    # Execute a single tick and compare results
    pline.tick()
    y = pline.get_object("y")
    assert np.array_equal(y, np.matmul(m, x))

def test_conv1d():
    # TODO: enable execute_ops = True, and compare results

    # A 1D-convolution with one layer (simplest case)
    #
    # For N=12, K=3, zero padding, the code looks simething like this:
    #
    # Stage s1:
    #     for o1 ← range(0, 10) {
    #         in2[o1,:] ← MXV(in1[o1:(o1 + 3),:])
    #     }
    # Stage s2:
    #     for o2 ← range(0, 8) {
    #         out2[o2,:] ← MXV(in2[o2:(o2 + 3),:])
    #     }
    #

    # Example values
    # N: in1 size
    # K: kernel size
    # P: padding
    eg_vals = {'n': 10, 'k': 3, 'p': 1}

    stage1 = pl.Stage(pl.StageInfo(
        rd_a = "[n,k,p] -> { S1[o1] -> in1[j] : 0 <= o1 < ((n - k + 2*p) + 1) and o1 <= j < o1 + k }",
        wr_a = "[n,k,p] -> { S1[o1] -> in2[j] : 0 <= o1 < ((n - k + 2*p) + 1) and j = o1 + p}"
    ), eg_vals)


    stage2 = pl.Stage(pl.StageInfo(
        rd_a = "[n,k,p] -> { S2[o2] -> in2[j] : 0 <= o2 < (n-k+2*p) and  o2 <= j < o2 + k }"
    ), eg_vals)

    objects = {
        'in1': eval("(n + 2*p,)", eg_vals),
        'in2': eval("(n - k + 2*p + 1 + 2*p,)", eg_vals),
    }
    pprint(objects)

    pline = pl.Pipeline([stage1, stage2], objects)

    for i in range(13):
        pline.tick()


def test_conv2d():
    conv1_ps = conv.ConvParams(
        i = conv.ConvInParams(w=32, h=32, d=3),
        f = conv.ConvFiltParams(w=3, h=3, d=3, l=16),
        p = 1,
        s = 1,
        p_out = 0)

    s1_rdwr_a = conv1_ps.get_rd_wr_a(s_id=1, vin_id=1, vout_id=2)
    stage1 = pl.Stage(pl.StageInfo(
        rd_a = s1_rdwr_a[0],
        wr_a = s1_rdwr_a[1],
    ))

    objs = {
        'V1': conv1_ps.get_in_shape(),
        'V2': conv1_ps.get_out_shape(),
    }

    p = pl.Pipeline([stage1], objs, execute_ops=True)

    filters1 = np.random.rand(*conv1_ps.get_filters_shape())
    image1 = np.random.rand(*conv1_ps.get_image_shape())
    image1 = np.pad(image1, conv1_ps.get_padding())

    output_simple = conv.conv2d_simple(image1, filters1, conv1_ps)
    output_mxv = conv.conv2d_mxv(image1, filters1, conv1_ps)
    np.testing.assert_allclose(output_simple, output_mxv)

    filters_m = filters1.reshape(conv1_ps.eval("(f.l, f.d*f.h*f.w)"))
    cconf = pl.CoreConf(filters_m)

    vals1 = p.get_object('V1')
    vals1[...] = image1
    p.configure([cconf])

    for _ in range(conv1_ps.o.h*conv1_ps.o.w):
        p.tick()
    vals2 = p.get_object('V2')
    np.testing.assert_array_equal(output_mxv, vals2)
