from flask import Flask, request, jsonify
import pickle
import numpy as np

model_file = 'credit_object.pkl'
token = 'KOLA2019#'


criteria = ['Gender', 'Age', 'Bank_account', 'Phone range']


app = Flask(__name__)

@app.route('/', methods=['POST', 'GET'])
def index_page():
	return jsonify({'message': 'Je teste la construction d\'api'})


# Authentification process
def auth(request):
	# Authentifcation process
	if 'Authorization' not in request.headers.keys():
		return jsonify({'Score':'Not authorization'})
	if request.headers['Authorization'] != token:
		return jsonify({'Score': 'Authentification failed'})
	return None



# Endpoint to compute the credit score and the amount available for tne borrower
@app.route('/predict', methods=['POST', 'GET'])
def predict_logic():
	
	auth_result = auth(request)
	if auth_result is not None:
		return auth_result

	# Compute the score
	elt = request.get_json(force=True)
	elt = prepare_data(elt)

	# Pick the right model according to the value of 'Savings'  
	if elt['Savings'] == -1: # The user is not registered in any tontine in KW
		_, model = deserialize_model(model_file)
		elt = {key:value for key, value in elt.items() if key != 'Savings'} # Remove the "Savings" among the others criteria
	else: # The user is registered in at least one tontine in KW
		model, _ = deserialize_model(model_file)
		#elt['Savings'] = elt['Savings']

	infos = compute_score(elt, *model)
	return infos


def prepare_data(row):
	
	# Encoding Age variable
	if row['Age'] < 25:
		row['Age'] = '18-24'
	elif row['Age'] in range(25,35):
		row['Age'] = '25-34'
	elif row['Age'] in range(35,45):
		row['Age'] = '35-44'
	elif row['Age'] in range(45,55):
		row['Age'] = '45-54'
	elif row['Age'] in range(55,65):
		row['Age'] = '55-64'
	else:
		row['Age'] = '65+'


	# Encoding Phone range variable
	if row['Phone range'] <= 32:
		row['Phone range'] = 'Budget'
	elif 32 < row['Phone range'] and row['Phone range'] <= 128:
		row['Phone range'] = 'Midrange'
	else:
		row['Phone range'] = 'Flagship'

	return row


def deserialize_model(model_file):
	with open(model_file, mode='rb') as file:
		model1, model2 = pickle.load(file)
	return tuple(model1.values()), tuple(model2.values())


def normalize(elt, norm_params):
    for criterion in norm_params.keys():
        elt[criterion] = elt[criterion] / norm_params[criterion]
    return elt


def normalize_score(score, Min, Max):
	# First normalization : Put the score between [0, 1]
	score = (score - Min)/(Max - Min)
	score = score if score <= 1.0 else 1.0
	
	# Second normalization : Put the score between [MIN, MAX]
	MIN = 300
	MAX = 860
	return score * MAX + (1 - score) * MIN 	


def compute_score(elt, Options, weights, Min, Max, norm_params):
	score = 0
	row = normalize(elt, norm_params)
	for criterion in row:
		if criterion in criteria: # For categorical variables
			score += weights[criterion]*Options[criterion][row[criterion]]
		else: # For numerical criterion
			score += weights[criterion]*float(row[criterion]) 
	    	


	score = normalize_score(score, Min, Max)

	# Compute the amount available
	amount = lend(score)

	# Compute the maximum values for normalization
	max_age = Options['Age'].values.max()
	max_gender = Options['Gender'].values.max()
	max_bank_account = Options['Bank_account'].values.max()
	max_phone_range = Options['Phone range'].values.max()


	age = Options['Age'][row['Age']]
	gender = Options['Gender'][row['Gender']]
	bank_account = Options['Bank_account'][row['Bank_account']]
	phone = Options['Phone range'][row['Phone range']]
	repayment = float(row['Due date - repayment date'])
	vol_trans = float(row['Volume of transactions'])
	communication = float(row['Communication'])

	# Normalisation constant

	age = age/max_age
	gender = gender/max_gender
	bank_account = bank_account/max_bank_account
	phone = phone/max_phone_range
	repayment = 1.0 if repayment > 1.0 else repayment
	vol_trans = 1.0 if vol_trans > 1.0 else vol_trans
	communication = 1.0 if communication > 1.0 else communication

	try:
		savings = float(row['Savings'])
		savings = 1.0 if savings > 1.0 else savings
	except:
		pass

	if 'Savings' in elt.keys():
		return jsonify({
					'Amount available': int(amount),
					'Score': int(score),
		 			'repayment': round(repayment, 2),
		   			'vol_trans': round(vol_trans, 2),
		   			'bank_account': round(bank_account, 2),
		            'communication': round(communication, 2),
		            'age': round(age, 2),
		            'gender': round(gender, 2),
		            'Phone range': round(phone, 2),
		            'Savings': round(savings, 2)
		            })
	else:
		return jsonify({
					'Amount available': int(amount),
					'Score': int(score),
		 			'repayment': round(repayment, 2),
		   			'vol_trans': round(vol_trans, 2),
		   			'bank_account': round(bank_account, 2),
		            'communication': round(communication, 2),
		            'age': round(age, 2),
		            'gender': round(gender, 2),
		            'Phone range': round(phone, 2),
			            })

def lend(score, for_guarantor=False):

	MIN = 300 # Min value of credit score 
	MAX = 860 # Max value of credit score
	LOWER = .5 # Lower bound 
	UPPER = .8 # Upper bound
	ALPHA = 1 # 
	MAX_LOAN_SIZE = 20_000 # Maximum of the loan size
	epsilon = .5 # To handle random loans


	score = (score - MIN)/(MAX - MIN)

	if score < LOWER:
		if np.random.rand() > epsilon and not for_guarantor:
			amount = ALPHA*score*MAX_LOAN_SIZE
		else:
			amount = 0
	elif LOWER <= score and score <= UPPER:
		amount = ALPHA*score*MAX_LOAN_SIZE
	else:
		amount = MAX_LOAN_SIZE

	return amount



# Endpoint to compute the amount available for the user based on his score
@app.route('/amount_available', methods=['POST'])
def comute_amount_available():

	auth_result = auth(request)
	if auth_result is not None:
		return auth_result

	# Get the score send by the user
	elt = request.get_json(force=True)

	return jsonify({'Amount available': lend(elt['score'], for_guarantor=True)})


if __name__ == "__main__":
	app.run(debug=True, host='0.0.0.0', port=5000)