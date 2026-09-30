"""
Teste manual da nova consulta de preço atual da EGDATA.

A partir da raiz do projeto:

    python -m backend.tests.manual.teste_egdata_preco
"""

from backend.servicos.egdata import buscar_preco_atual


OFERTAS_TESTE = {
    "The Witcher 3": "9064fdd49de04718abe631788ad5a759",
    "Hades": "2ae6edb2223c4f8c97e9839b5b6497bb",
}


def main():
    for nome, offer_id in OFERTAS_TESTE.items():
        print("=" * 70)
        print(nome)
        print("=" * 70)

        try:
            dados = buscar_preco_atual(offer_id)

            print(f"Offer ID:        {dados['offer_id']}")
            print(f"Preço atual:     R$ {dados['preco']:.2f}")
            print(
                f"Preço original:  "
                f"R$ {dados['preco_sem_desconto']:.2f}"
            )
            print(f"Desconto:        {dados['desconto']}%")
            print(f"Promoção início: {dados['promocao_inicio']}")
            print(f"Promoção fim:    {dados['promocao_fim']}")
            print(f"Promoção ID:     {dados['promocao_id']}")
            print(f"Promoção nome:   {dados['promocao_nome']}")
            print(f"Atualizado em:   {dados['updated_at']}")

        except Exception as erro:
            print(f"ERRO: {erro}")

        print()


if __name__ == "__main__":
    main()
