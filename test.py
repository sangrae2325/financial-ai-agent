from collectors.news import fetch_news_list

news = fetch_news_list()

print(len(news))

for article in news[:5]:
    print(article)