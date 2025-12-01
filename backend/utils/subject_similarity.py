from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def subject_similarity(subject1, subject2):
    texts = [subject1.lower(), subject2.lower()]
    vectorizer = TfidfVectorizer().fit_transform(texts)
    vectors = vectorizer.toarray()
    
    sim_score = cosine_similarity([vectors[0]], [vectors[1]])[0][0]
    return sim_score * 100  # return percentage
