def test_qdrant():
    from qdrant_client import QdrantClient

    client = QdrantClient(host="localhost", port=6333)

    try:
        collections = client.get_collections()
        print("Qdrant 连接成功！当前集合列表：", collections)
    except Exception as e:
        print("连接失败：", e)

def test_cross_encoder():
    from sentence_transformers import CrossEncoder

    model = CrossEncoder('BAAI/bge-reranker-large')
    question = "什么是机器学习？"
    sentence_pairs = [
        (question, "机器学习是人工智能的一个分支，它使计算机系统能够从数据中学习并在没有明确编程的情况下做出预测或决策。它使用算法来分析数据、识别模式并调整模型参数以提高性能。"),
        (question, "机器学习是让机器人学习。"),
        (question, "机器学习是指人们的学习方式太过僵化，并没有真正理解知识。")
    ]
    scores = model.predict(sentence_pairs)
    print("CrossEncoder 模型预测结果：", scores)

if __name__ == "__main__":
    # test_qdrant()
    test_cross_encoder()