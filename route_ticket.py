from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

import os
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

ticket = "Our API integration started returning 500 errors on every request about 20 minutes ago, and we can't process any customer orders until this is fixed."

with TypeSafeClient(model="jev-latest", api_key=os.getenv("TYPESAFE_API_KEY")) as client:  # Reads TYPESAFE_API_KEY.
    response = client.system_one(
        state=ticket,
        questions={
            "department": Choice(
                instructions="Which team should handle this",
                criteria={
                    "billing": "Payment or subscription issues",
                    "technical": "Bugs or integration problems",
                    "sales": "Pricing or account questions",
                },
            ),
            "frustration": Score(
                instructions="How frustrated the customer appears",
                criteria=[
                    "Calm, just stating facts",
                    "Frustrated but civil",
                    "Very angry, strong language",
                ],
            ),
            "is_urgent": Noul(
                instructions="The message conveys urgency or time-sensitivity",
            ),
        },
    )

print(response.choices["department"].choice)
print(response.scores["frustration"].score)
print(response.nouls["is_urgent"].noul)