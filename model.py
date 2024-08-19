import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

class SentimentAnalyzer:
    def __init__(self):
        self.model = AutoModelForSequenceClassification.from_pretrained('christian-phu/bert-finetuned-japanese-sentiment')
        self.tokenizer = AutoTokenizer.from_pretrained('christian-phu/bert-finetuned-japanese-sentiment', model_max_length=512)

    def evaluate_diary(self, diary_text):
        inputs = self.tokenizer(diary_text, padding=True, truncation=True, return_tensors='pt', max_length=30)
        with torch.no_grad():
            outputs = self.model(**inputs)
        logits = outputs.logits

        probabilities = torch.softmax(logits, dim=1)[0]
        sentiment_label = self.model.config.id2label[torch.argmax(probabilities).item()]
        
        # positiveの確率を取得し、0-100のスコアに変換
        positive_prob = probabilities[self.model.config.label2id['positive']].item()
        score = round(positive_prob * 100)

        return sentiment_label, score

sentiment_analyzer = SentimentAnalyzer()

def evaluate_diary(diary_text):
    sentiment_label, score = sentiment_analyzer.evaluate_diary(diary_text)
    return sentiment_label, score

if __name__ == '__main__':
    print("日記を入力してください（終了するには 'exit' と入力）：")
    while True:
        diary = input("日記: ")
        if diary.lower() == 'exit':
            break
        if len(diary) > 30:
            print("Error: 日記は30文字以内で入力してください。")
        else:
            sentiment_label, score = evaluate_diary(diary)
            print('*' * 50)
            print(f'日記：{diary}')
            print(f'感情：{sentiment_label}')
            print(f'スコア: {score}')