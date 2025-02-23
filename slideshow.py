import sys
import os
import gurobipy as gp
from gurobipy import GRB
from functools import partial

# Classe pour les données passées à la fonction de callback
class CallbackData:
    def __init__(self):
        self.last_gap_change_time = GRB.INFINITY
        self.last_gap = GRB.INFINITY

# Fonction de callback
def callback(model, where, *, cbdata):
    if where != GRB.Callback.MIP:
        return
    if model.cbGet(GRB.Callback.MIP_SOLCNT) == 0:
        return
    if model.cbGet(GRB.Callback.MIP_OBJBST) == 0:
        return
    gap = abs(model.cbGet(GRB.Callback.MIP_OBJBST) - model.cbGet(GRB.Callback.MIP_OBJBND))/model.cbGet(GRB.Callback.MIP_OBJBST)

    if abs(gap - cbdata.last_gap) > epsilon_to_compare_gap:
        cbdata.last_gap_change_time = model.cbGet(GRB.Callback.RUNTIME)
        cbdata.last_gap = gap
        return
    elif model.cbGet(GRB.Callback.RUNTIME) - cbdata.last_gap_change_time > time_from_best:
        model.terminate()

if __name__ == "__main__":
    # Vérifie que l'argument est fourni
    if len(sys.argv) < 2:
        print("Utilisation : python slideshow.py [relative/path/to/dataset.txt]")
        sys.exit(1)

    dataset_path = sys.argv[1]

    # Vérifie que le fichier existe
    if not os.path.isfile(dataset_path):
        print(f"Erreur : Le fichier '{dataset_path}' n'existe pas.")
        sys.exit(1)

    # Vérifie que c'est bien un fichier .txt
    if not dataset_path.lower().endswith(".txt"):
        print("Erreur : Le fichier doit être un fichier .txt")
        sys.exit(1)

    # Lire et afficher le contenu du fichier
    with open(dataset_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    # Récupération des données

    # Nombre de photos
    nb_photos = int(lines[0])
    # print(nb_photos)

    orientations = []
    nb_tags_by_photo = []
    tags_by_photo = []
    nb_slides_max = 0
    for i in range(1, nb_photos + 1):
        # Orientation et calcul du nombre de slides maximum
        # 2: H, 1: V
        # nb_slides_max = nb_photos_horizontales + partie entiere (nb_photos_verticales / 2)
        if lines[i].split()[0] == "H":
            orientations.append(2)
            nb_slides_max += 1
        else:
            orientations.append(1)
            nb_slides_max += 1/2

        # Nombre de tags par photo
        nb_tags_by_photo.append(int(lines[i].split()[1]))

        # Tags
        tags = []
        for j in range(2, nb_tags_by_photo[i - 1] + 2):
            tags.append(lines[i].split()[j])
        tags_by_photo.append(tags)

    nb_slides_max = int(nb_slides_max)
    # print(nb_slides_max)

    # print(orientations)
    # print(nb_tags_by_photo)
    # print(tags_by_photo)

    # Liste de tous les tags de toutes les photos
    all_tags = []
    for tags in tags_by_photo:
        for tag in tags:
            if tag not in all_tags:
                all_tags.append(tag)
    # print(all_tags)

    # Nombre de tags
    nb_tags = len(all_tags)
    # print(nb_tags)

    # Matrice des tags par photo
    tags_matrix = []
    for i in range(nb_photos):
        tags = []
        for j in range(nb_tags):
            if all_tags[j] in tags_by_photo[i]:
                tags.append(1)
            else:
                tags.append(0)
        tags_matrix.append(tags)
    # print(tags_matrix)

    with gp.Model("slideshow") as model:
            
            # Variables

            # 1 si la photo i est dans la slide s en position p, 0 sinon
            Mat_photo_slide_position = model.addVars(nb_photos, nb_slides_max, 2, vtype=GRB.BINARY, name="Mat_photo_slide_position")

            # 1 si le tag t est dans la slide s, 0 sinon
            Mat_slide_tags = model.addVars(nb_slides_max, nb_tags, vtype=GRB.BINARY, name="Mat_slide_tags")

            # 1 si la slide s est utilisée, 0 sinon
            Utilisation_slide = model.addVars(nb_slides_max, vtype=GRB.BINARY, name="Utilisation_slide")

            # 1 si le tag t est commun entre les slides s et s+1, 0 sinon
            Tags_communs = model.addVars(nb_slides_max - 1, nb_tags, vtype=GRB.BINARY, name="Tags_communs")

            # 1 si le tag t est non commun entre les slides s et s+1, 0 sinon
            Tags_non_communs1 = model.addVars(nb_slides_max - 1, nb_tags, vtype=GRB.BINARY, name="Tags_non_communs1")

            # 1 si le tag t est non commun entre les slides s+1 et s, 0 sinon
            Tags_non_communs2 = model.addVars(nb_slides_max - 1, nb_tags, vtype=GRB.BINARY, name="Tags_non_communs2")

            # Nombre de tags communs entre deux slides consécutives
            Tags_communs_totaux = model.addVars(nb_slides_max - 1, vtype=GRB.INTEGER, name="Tags_communs_totaux")

            # Tags non communs présents dans la slide s mais pas dans la slide s+1
            Tags_non_communs1_totaux = model.addVars(nb_slides_max - 1, vtype=GRB.INTEGER, name="Tags_non_communs1_totaux")

            # Tags non communs présents dans la slide s+1 mais pas dans la slide s
            Tags_non_communs2_totaux = model.addVars(nb_slides_max - 1, vtype=GRB.INTEGER, name="Tags_non_communs2_totaux")

            # Minimum entre les tags communs et les tags non communs pour chaque slide
            Min = model.addVars(nb_slides_max - 1, vtype=GRB.INTEGER, name="Min")

            # Contraintes

            # Chaque photo doit être utilisée maximum une fois
            for i in range(nb_photos):
                model.addConstr(Mat_photo_slide_position.sum(i, '*', '*') <= 1)

            # Les NS premières slides doivent être utilisées consécutivement
            for s in range(nb_slides_max-1):
                model.addConstr(Utilisation_slide[s] >= Utilisation_slide[s+1])
            
            # Une slide est utilisée ssi elle contient une photo
            for s in range(nb_slides_max):
                model.addConstr(Utilisation_slide[s] * 2 >= Mat_photo_slide_position.sum('*', s, '*')) # 2 car une slide contient au plus 2 photos
                model.addConstr(Utilisation_slide[s] <= Mat_photo_slide_position.sum('*', s, '*'))

            # Les tags des slides sont l'union des tags des photos composant la slide
            for s in range(nb_slides_max):
                for t in range(nb_tags):
                    model.addConstr(Mat_slide_tags[s, t] >= gp.quicksum(Mat_photo_slide_position[i, s, 0] * tags_matrix[i][t] for i in range(nb_photos)))
                    model.addConstr(Mat_slide_tags[s, t] >= gp.quicksum(Mat_photo_slide_position[i, s, 1] * tags_matrix[i][t] for i in range(nb_photos)))
                    model.addConstr(Mat_slide_tags[s, t] <= gp.quicksum(Mat_photo_slide_position[i, s, 0] * tags_matrix[i][t] for i in range(nb_photos)) + gp.quicksum(Mat_photo_slide_position[i, s, 1] * tags_matrix[i][t] for i in range(nb_photos)))

            # Les tags communs entre deux slides
            for s in range(nb_slides_max-1):
                for t in range(nb_tags):
                    # model.addConstr(Tags_communs[s, t] == Mat_slide_tags[s, t] * Mat_slide_tags[s+1, t])
                    model.addConstr(Tags_communs[s, t] <= Mat_slide_tags[s, t])
                    model.addConstr(Tags_communs[s, t] <= Mat_slide_tags[s+1, t])
                    model.addConstr(Tags_communs[s, t] >= Mat_slide_tags[s, t] + Mat_slide_tags[s+1, t] - 1)


            # Les tags non communs présents dans la slide s mais pas dans la slide s+1
            for s in range(nb_slides_max-1):
                for t in range(nb_tags):
                    # model.addConstr(Tags_non_communs1[s, t] == Mat_slide_tags[s, t] * (1 - Mat_slide_tags[s+1, t]) * Utilisation_slide[s+1])
                    model.addConstr(Tags_non_communs1[s, t] <= Mat_slide_tags[s, t])
                    model.addConstr(Tags_non_communs1[s, t] <= 1 - Mat_slide_tags[s+1, t])
                    model.addConstr(Tags_non_communs1[s, t] <= Utilisation_slide[s+1])
                    model.addConstr(Tags_non_communs1[s, t] >= Mat_slide_tags[s, t] - Mat_slide_tags[s+1, t] + Utilisation_slide[s+1] - 1)

            # Les tags non communs présents dans la slide s+1 mais pas dans la slide s
            for s in range(nb_slides_max-1):
                for t in range(nb_tags):
                    # model.addConstr(Tags_non_communs2[s, t] == (1 - Mat_slide_tags[s, t]) * Mat_slide_tags[s+1, t])
                    model.addConstr(Tags_non_communs2[s, t] <= 1 - Mat_slide_tags[s, t])
                    model.addConstr(Tags_non_communs2[s, t] <= Mat_slide_tags[s+1, t])
                    model.addConstr(Tags_non_communs2[s, t] >= - Mat_slide_tags[s, t] + Mat_slide_tags[s+1, t])

            # Les tags communs totaux entre deux slides
            for s in range(nb_slides_max-1):
                model.addConstr(Tags_communs_totaux[s] == Tags_communs.sum(s, '*'))

            # Les tags non communs totaux présents dans la slide s mais pas dans la slide s+1
            for s in range(nb_slides_max-1):
                model.addConstr(Tags_non_communs1_totaux[s] == Tags_non_communs1.sum(s, '*'))

            # Les tags non communs totaux présents dans la slide s+1 mais pas dans la slide s
            for s in range(nb_slides_max-1):
                model.addConstr(Tags_non_communs2_totaux[s] == Tags_non_communs2.sum(s, '*'))

            # Calcul du minimum entre les tags communs et les tags non communs pour chaque slide
            for s in range(nb_slides_max-1):
                model.addConstr(Min[s] == gp.min_(Tags_communs_totaux[s], Tags_non_communs1_totaux[s], Tags_non_communs2_totaux[s]))    

            # Pour chaque slide, soit deux photos verticales, soit une photo horizontale
            for s in range(nb_slides_max):
                model.addConstr(gp.quicksum(Mat_photo_slide_position[i, s, p] * orientations[i] for i in range(nb_photos) for p in range(2)) == 2 * Utilisation_slide[s])

            # Le diaporama contient au moins une slide
            model.addConstr(Utilisation_slide[0] == 1)

            # Fonction objectif : maximiser la somme des minimums
            model.setObjective(Min.sum('*'), GRB.MAXIMIZE)

            # Global variables used in the callback function
            time_from_best = 3600
            epsilon_to_compare_gap = 1e-4

            # Initialize data passed to the callback function
            callback_data = CallbackData()
            callback_func = partial(callback, cbdata=callback_data)

            model.setParam("BestObjStop", 82)

            model.optimize(callback_func)

            # if model.status == GRB.INF_OR_UNBD:
            #     print("Le modèle est infaisable. Calcul de l'IIS...")
            #     model.computeIIS()
            #     model.write("infeasible.ilp")  # Génère un fichier indiquant les contraintes conflictuelles

            # Compte le nombre de slides utilisées
            nb_slides = 0
            for s in range(nb_slides_max):
                if Utilisation_slide[s].X == 1:
                    nb_slides += 1

            # Création du fichier de sortie
            with open("slideshow.sol", "w") as f:
                
                # Écriture du nombre de slides en première ligne
                f.write(str(nb_slides) + "\n")

                # Écriture des photos composant chaque slide
                booleen_deja_une_photo_dans_la_slide = False

                for s in range(nb_slides_max):
                    for i in range(nb_photos):
                        for p in range(2):
                            if Mat_photo_slide_position[i, s, p].X == 1:
                                if booleen_deja_une_photo_dans_la_slide:
                                    f.write(" ")
                                f.write(str(i))
                                booleen_deja_une_photo_dans_la_slide = True
                                break
                    f.write("\n")
                    booleen_deja_une_photo_dans_la_slide = False

            print("Solution enregistrée dans 'slideshow.sol'")


            



            





            

            