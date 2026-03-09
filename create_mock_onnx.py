import onnx
from onnx import helper
from onnx import TensorProto

# Define a mock model that just outputs [5.0, 0.0] constantly for fire
X = helper.make_tensor_value_info('input', TensorProto.FLOAT, [1, 3, 224, 224])
Y = helper.make_tensor_value_info('logits', TensorProto.FLOAT, [1, 2])

# Constant shape and values
const_tensor = helper.make_tensor(
    name='const_tens',
    data_type=TensorProto.FLOAT,
    dims=[1, 2],
    vals=[5.0, 0.0]
)

node_const = helper.make_node(
    'Constant',
    inputs=[],
    outputs=['const_tens_out'],
    value=const_tensor
)

node_identity = helper.make_node(
    'Identity',
    inputs=['const_tens_out'],
    outputs=['logits']
)

graph_def = helper.make_graph(
    [node_const, node_identity],
    'mock_model',
    [X],
    [Y]
)

model_def = helper.make_model(graph_def, producer_name='mock_maker', ir_version=8)
model_def.opset_import[0].version = 13
onnx.save(model_def, '/tmp/fire_detection.onnx')
print("Mock ONNX saved!")
