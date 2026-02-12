"""
SCRIPT DE NETTOYAGE COMPLET - PROJET ID IMMOBILIER
Prend en compte :
- Les 3 niveaux de champs (Essentiels, Utiles, Bonus)
- La structure complète de la base de données
- Tous les enrichissements nécessaires
"""

import pandas as pd
import numpy as np
import re
from datetime import datetime
import json


class IDImmobilierCleaner:
    """
    Nettoyeur complet pour le projet ID Immobilier
    Respecte les 3 niveaux de champs et la structure SQL
    """
    
    def __init__(self):
        # Configuration
        self.surface_lot_standard = 350  # 1 lot standard au Togo ≈ 350 m²
        
        # Liste des quartiers de Lomé (à compléter)
        self.quartiers_lome = [
            'adakpamé', 'adidogomé', 'akodesséwa', 'adeticopé', 'akodessewa',
            'anfoin', 'avédji', 'djidjolé', 'noèpé', 'kpala', 'kpalimé',
            'zanguéra', 'wonyomé', 'nanegbé', 'totsi', 'bè', 'agoe',
            'hedziranawoe', 'adewui', 'kagomé', 'tokoin', 'nyekonakpoe'
        ]
        
        # Mapping des champs selon les 3 niveaux
        self.niveaux_champs = {
            'niveau_1_essentiels': [
                'id',
                'marketplace_listing_title',
                'custom_title',
                'listing_price/amount',
                'location/reverse_geocode/city',
                'listingUrl',
                'is_sold',
                'is_live'
            ],
            'niveau_2_utiles': [
                'primary_listing_photo/photo_image_url',
                'marketplace_listing_category_id',
                'location/reverse_geocode/state'
            ],
            'niveau_3_bonus': [
                'facebookUrl',
                'listing_price/formatted_amount',
                'location/reverse_geocode/city_page/display_name',
                'is_pending',
                'is_hidden'
            ]
        }
    
    # ============================================
    # NIVEAU 1 : EXTRACTION DES CHAMPS ESSENTIELS
    # ============================================
    
    def extraire_surface(self, titre):
        """
        Extraire la surface depuis le titre
        Patterns supportés : 1/4 lot, 1 lot, 350 m²
        """
        if not titre or pd.isna(titre):
            return None
        
        titre = str(titre).lower()
        
        # Pattern 1: "1/4 de lot", "1/2 lot", "1/8 lot"
        match = re.search(r'(\d+)/(\d+)\s*(?:de\s*)?lots?', titre)
        if match:
            numerateur = int(match.group(1))
            denominateur = int(match.group(2))
            return (numerateur / denominateur) * self.surface_lot_standard
        
        # Pattern 2: "1 lot", "2 lots", "1lot"
        match = re.search(r'(\d+)\s*lots?', titre)
        if match:
            nb_lots = int(match.group(1))
            return nb_lots * self.surface_lot_standard
        
        # Pattern 3: "350 m²", "350m2", "350 mètres carrés"
        match = re.search(r'(\d+)\s*(?:m[²2]|mètres?\s*carrés?)', titre)
        if match:
            return int(match.group(1))
        
        # Pattern 4: "1lot et 1/4" (exemple: "1lot et 1/4 à Nanegbe")
        match = re.search(r'(\d+)\s*lots?\s*et\s*(\d+)/(\d+)', titre)
        if match:
            lots_entiers = int(match.group(1))
            numerateur = int(match.group(2))
            denominateur = int(match.group(3))
            return (lots_entiers + numerateur / denominateur) * self.surface_lot_standard
        
        return None
    
    def extraire_quartier(self, titre):
        """Extraire le quartier depuis le titre"""
        if not titre or pd.isna(titre):
            return 'Non spécifié'
        
        titre_lower = str(titre).lower()
        
        # Rechercher chaque quartier connu
        for quartier in self.quartiers_lome:
            if quartier in titre_lower:
                return quartier.capitalize()
        
        return 'Non spécifié'
    
    def nettoyer_prix(self, prix, titre):
        """
        Nettoyer et valider le prix
        Gère les prix aberrants et tente extraction depuis le titre
        """
        # Convertir en float si nécessaire
        try:
            prix = float(prix) if pd.notna(prix) else 0
        except:
            prix = 0
        
        # Si prix invalide, tenter extraction depuis titre
        if pd.isna(prix) or prix <= 0 or prix < 100000:
            if titre and not pd.isna(titre):
                # Pattern: "3,500,000" ou "3 500 000" ou "3500000"
                match = re.search(r'(\d{1,3}(?:[,\s]\d{3})+)\s*(?:fcfa|cfa|f)?', 
                                str(titre).lower())
                if match:
                    prix_str = match.group(1).replace(',', '').replace(' ', '')
                    try:
                        prix = float(prix_str)
                    except:
                        pass
                
                # Pattern: "X millions" ou "X M"
                match = re.search(r'(\d+(?:\.\d+)?)\s*(?:millions?|m)\s*(?:fcfa|cfa|f)?', 
                                str(titre).lower())
                if match:
                    prix = float(match.group(1)) * 1000000
        
        # Filtrer les prix aberrants (< 100 000 FCFA pour un terrain)
        if prix > 0 and prix < 100000:
            return None
        
        return prix if prix > 0 else None
    
    def identifier_type_bien(self, titre):
        """Identifier le type de bien immobilier"""
        if not titre or pd.isna(titre):
            return 'Inconnu'
        
        titre_lower = str(titre).lower()
        
        # Ordre de priorité pour éviter les faux positifs
        if 'terrain' in titre_lower:
            return 'Terrain'
        elif any(word in titre_lower for word in ['villa', 'duplex']):
            return 'Villa'
        elif 'maison' in titre_lower:
            return 'Maison'
        elif any(word in titre_lower for word in ['appartement', 'studio', 'f1', 'f2', 'f3', 'f4']):
            return 'Appartement'
        elif 'immeuble' in titre_lower:
            return 'Immeuble'
        elif 'bureau' in titre_lower or 'commercial' in titre_lower:
            return 'Commercial'
        
        # Par défaut pour Facebook Marketplace recherche terrain
        return 'Terrain'
    
    def identifier_type_offre(self, titre):
        """Identifier le type d'offre (Vente ou Location)"""
        if not titre or pd.isna(titre):
            return 'Vente'
        
        titre_lower = str(titre).lower()
        
        if any(word in titre_lower for word in ['louer', 'location', 'à louer', 'en location']):
            return 'Location'
        
        return 'Vente'
    
    # ============================================
    # NIVEAU 2 : ENRICHISSEMENT DES DONNÉES
    # ============================================
    
    def generer_titre_complet(self, row):
        """Générer un titre complet en combinant les champs disponibles"""
        titre_parts = []
        
        if pd.notna(row.get('marketplace_listing_title')):
            titre_parts.append(str(row['marketplace_listing_title']))
        
        if pd.notna(row.get('custom_title')):
            titre_parts.append(str(row['custom_title']))
        
        return ' '.join(titre_parts).strip() if titre_parts else 'Sans titre'
    
    def extraire_ville(self, row):
        """Extraire la ville avec fallback"""
        # Priorité 1: location/reverse_geocode/city
        if pd.notna(row.get('location/reverse_geocode/city')):
            return str(row['location/reverse_geocode/city'])
        
        # Priorité 2: location/reverse_geocode/city_page/display_name
        if pd.notna(row.get('location/reverse_geocode/city_page/display_name')):
            display = str(row['location/reverse_geocode/city_page/display_name'])
            return display.split(',')[0].strip()  # "Lomé, Togo" -> "Lomé"
        
        return 'Lomé'  # Par défaut
    
    def determiner_statut(self, row):
        """Déterminer le statut de l'annonce"""
        if row.get('is_sold') == 'true' or row.get('is_sold') == True:
            return 'Vendue'
        elif row.get('is_live') == 'true' or row.get('is_live') == True:
            return 'Active'
        elif row.get('is_pending') == 'true' or row.get('is_pending') == True:
            return 'En attente'
        elif row.get('is_hidden') == 'true' or row.get('is_hidden') == True:
            return 'Masquée'
        else:
            return 'Inconnue'
    
    # ============================================
    # FONCTION PRINCIPALE DE NETTOYAGE
    # ============================================
    
    def nettoyer_dataset(self, df):
        """
        Nettoyer le dataset complet
        Retourne un DataFrame avec la structure de la base de données
        """
        
        print("="*60)
        print("🚀 NETTOYAGE DATASET - PROJET ID IMMOBILIER")
        print("="*60)
        print(f"📊 Données initiales: {len(df)} lignes\n")
        
        # Créer DataFrame de travail
        df_clean = df.copy()
        
        # ============================================
        # ÉTAPE 1 : CHAMPS NIVEAU 1 (ESSENTIELS)
        # ============================================
        print("🔹 ÉTAPE 1 : Extraction des champs essentiels")
        
        # 1.1 Titre complet
        df_clean['titre_complet'] = df_clean.apply(self.generer_titre_complet, axis=1)
        print("   ✓ Titres générés")
        
        # 1.2 ID
        df_clean['id_bien'] = df_clean['id'].astype(str)
        print("   ✓ ID extraits")
        
        # 1.3 Prix
        df_clean['prix_fcfa'] = df_clean.apply(
            lambda row: self.nettoyer_prix(
                row.get('listing_price/amount'), 
                row['titre_complet']
            ), axis=1
        )
        print(f"   ✓ Prix nettoyés ({df_clean['prix_fcfa'].notna().sum()}/{len(df_clean)} valides)")
        
        # 1.4 Ville
        df_clean['ville'] = df_clean.apply(self.extraire_ville, axis=1)
        print("   ✓ Villes extraites")
        
        # 1.5 URL
        df_clean['url_annonce'] = df_clean['listingUrl'].fillna('')
        print("   ✓ URLs conservées")
        
        # 1.6 Statut
        df_clean['statut'] = df_clean.apply(self.determiner_statut, axis=1)
        print("   ✓ Statuts déterminés")
        
        # ============================================
        # ÉTAPE 2 : ENRICHISSEMENT (EXTRACTION)
        # ============================================
        print("\n🔹 ÉTAPE 2 : Enrichissement des données")
        
        # 2.1 Surface
        df_clean['surface_m2'] = df_clean['titre_complet'].apply(self.extraire_surface)
        surfaces_valides = df_clean['surface_m2'].notna().sum()
        print(f"   ✓ Surfaces extraites ({surfaces_valides}/{len(df_clean)} valides)")
        
        # 2.2 Quartier
        df_clean['quartier'] = df_clean['titre_complet'].apply(self.extraire_quartier)
        quartiers_trouves = (df_clean['quartier'] != 'Non spécifié').sum()
        print(f"   ✓ Quartiers identifiés ({quartiers_trouves}/{len(df_clean)} trouvés)")
        
        # 2.3 Type de bien
        df_clean['type_bien'] = df_clean['titre_complet'].apply(self.identifier_type_bien)
        print("   ✓ Types de biens identifiés")
        
        # 2.4 Type d'offre
        df_clean['type_offre'] = df_clean['titre_complet'].apply(self.identifier_type_offre)
        print("   ✓ Types d'offres identifiés")
        
        # 2.5 Prix au m² (INDICATEUR CLÉ)
        df_clean['prix_m2'] = df_clean.apply(
            lambda row: round(row['prix_fcfa'] / row['surface_m2'], 2)
            if pd.notna(row['surface_m2']) and row['surface_m2'] > 0 
               and pd.notna(row['prix_fcfa']) and row['prix_fcfa'] > 0
            else None,
            axis=1
        )
        prix_m2_valides = df_clean['prix_m2'].notna().sum()
        print(f"   ✓ Prix au m² calculés ({prix_m2_valides}/{len(df_clean)} valides)")
        
        # ============================================
        # ÉTAPE 3 : CHAMPS NIVEAU 2 & 3 (UTILES/BONUS)
        # ============================================
        print("\n🔹 ÉTAPE 3 : Ajout des champs complémentaires")
        
        # Source des données
        df_clean['source'] = 'Facebook Marketplace'
        
        # Date de collecte
        df_clean['date_collecte'] = datetime.now().strftime('%Y-%m-%d')
        
        # Coordonnées GPS (à enrichir ultérieurement)
        df_clean['latitude'] = None
        df_clean['longitude'] = None
        
        # Date de publication (à extraire si disponible)
        df_clean['date_publication'] = None
        
        # Photo (NIVEAU 2 - UTILE)
        df_clean['url_photo'] = df_clean.get('primary_listing_photo/photo_image_url', '')
        
        print("   ✓ Champs complémentaires ajoutés")
        
        # ============================================
        # ÉTAPE 4 : FILTRAGE DES DONNÉES VALIDES
        # ============================================
        print("\n🔹 ÉTAPE 4 : Filtrage des données valides")
        
        # Critères de validité pour ID Immobilier
        df_valide = df_clean[
            (df_clean['prix_fcfa'].notna()) &
            (df_clean['surface_m2'].notna()) &
            (df_clean['prix_fcfa'] > 0) &
            (df_clean['surface_m2'] > 0) &
            (df_clean['prix_m2'].notna())
        ].copy()
        
        print(f"   ✓ Données valides: {len(df_valide)} ({len(df_valide)/len(df)*100:.1f}%)")
        
        # ============================================
        # ÉTAPE 5 : STATISTIQUES
        # ============================================
        print("\n" + "="*60)
        print("📊 STATISTIQUES FINALES")
        print("="*60)
        
        if len(df_valide) > 0:
            print(f"Prix moyen au m²:     {df_valide['prix_m2'].mean():,.0f} FCFA")
            print(f"Prix médian au m²:    {df_valide['prix_m2'].median():,.0f} FCFA")
            print(f"Surface moyenne:      {df_valide['surface_m2'].mean():.0f} m²")
            print(f"Prix moyen total:     {df_valide['prix_fcfa'].mean():,.0f} FCFA")
            
            print(f"\n📍 Répartition par type de bien:")
            print(df_valide['type_bien'].value_counts())
            
            print(f"\n📋 Répartition par type d'offre:")
            print(df_valide['type_offre'].value_counts())
            
            print(f"\n🏙️ Top 10 quartiers:")
            quartiers = df_valide[df_valide['quartier'] != 'Non spécifié']['quartier'].value_counts().head(10)
            print(quartiers)
        else:
            print("⚠️ Aucune donnée valide après nettoyage")
        
        print("="*60)
        
        return df_valide
    
    # ============================================
    # EXPORT POUR BASE DE DONNÉES
    # ============================================
    
    def exporter_pour_bdd(self, df_clean, format='csv'):
        """
        Exporter selon la structure de la base de données
        Structure SQL définie dans le TDR
        """
        
        # Colonnes finales selon la structure SQL
        colonnes_bdd = [
            'id_bien',              # VARCHAR(50) PRIMARY KEY
            'titre_complet',        # TEXT
            'type_bien',           # VARCHAR(50)
            'type_offre',          # VARCHAR(20)
            'ville',               # VARCHAR(100)
            'quartier',            # VARCHAR(100)
            'surface_m2',          # FLOAT
            'prix_fcfa',           # DECIMAL(15,2)
            'prix_m2',             # DECIMAL(10,2) ⭐ INDICATEUR CLÉ
            'latitude',            # DECIMAL(10,8)
            'longitude',           # DECIMAL(11,8)
            'source',              # VARCHAR(50)
            'date_publication',    # DATE
            'date_collecte',       # DATE
            'url_annonce',         # TEXT
            'url_photo',           # TEXT (NIVEAU 2)
            'statut'               # VARCHAR(20)
        ]
        
        # Sélectionner uniquement les colonnes de la BDD
        df_export = df_clean[colonnes_bdd].copy()
        
        # Générer timestamp pour le nom de fichier
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if format == 'csv':
            filename = f'id_immobilier_clean_{timestamp}.csv'
            df_export.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"\n✅ Export CSV: {filename}")
        
        elif format == 'excel':
            filename = f'id_immobilier_clean_{timestamp}.xlsx'
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                # Feuille 1: Données nettoyées
                df_export.to_excel(writer, sheet_name='Données', index=False)
                
                # Feuille 2: Statistiques
                stats = self.generer_statistiques(df_clean)
                stats.to_excel(writer, sheet_name='Statistiques')
            
            print(f"\n✅ Export Excel: {filename}")
        
        elif format == 'json':
            filename = f'id_immobilier_clean_{timestamp}.json'
            df_export.to_json(filename, orient='records', force_ascii=False, indent=2)
            print(f"\n✅ Export JSON: {filename}")
        
        elif format == 'sql':
            filename = f'id_immobilier_insert_{timestamp}.sql'
            self.generer_insert_sql(df_export, filename)
            print(f"\n✅ Export SQL: {filename}")
        
        return filename
    
    def generer_statistiques(self, df):
        """Générer des statistiques pour Excel"""
        stats = {
            'Total lignes': len(df),
            'Prix moyen (FCFA)': df['prix_fcfa'].mean(),
            'Prix médian (FCFA)': df['prix_fcfa'].median(),
            'Prix moyen au m² (FCFA)': df['prix_m2'].mean(),
            'Surface moyenne (m²)': df['surface_m2'].mean(),
            'Terrains': (df['type_bien'] == 'Terrain').sum(),
            'Ventes': (df['type_offre'] == 'Vente').sum(),
            'Locations': (df['type_offre'] == 'Location').sum()
        }
        return pd.DataFrame([stats]).T.rename(columns={0: 'Valeur'})
    
    def generer_insert_sql(self, df, filename):
        """Générer des requêtes INSERT SQL"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("-- Script SQL pour ID Immobilier\n")
            f.write("-- Généré le: {}\n\n".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            f.write("CREATE TABLE IF NOT EXISTS biens_immobiliers (\n")
            f.write("    id_bien VARCHAR(50) PRIMARY KEY,\n")
            f.write("    titre_complet TEXT,\n")
            f.write("    type_bien VARCHAR(50),\n")
            f.write("    type_offre VARCHAR(20),\n")
            f.write("    ville VARCHAR(100),\n")
            f.write("    quartier VARCHAR(100),\n")
            f.write("    surface_m2 FLOAT,\n")
            f.write("    prix_fcfa DECIMAL(15,2),\n")
            f.write("    prix_m2 DECIMAL(10,2),\n")
            f.write("    latitude DECIMAL(10,8),\n")
            f.write("    longitude DECIMAL(11,8),\n")
            f.write("    source VARCHAR(50),\n")
            f.write("    date_publication DATE,\n")
            f.write("    date_collecte DATE,\n")
            f.write("    url_annonce TEXT,\n")
            f.write("    url_photo TEXT,\n")
            f.write("    statut VARCHAR(20)\n")
            f.write(");\n\n")
            
            for _, row in df.iterrows():
                values = []
                for col in df.columns:
                    val = row[col]
                    if pd.isna(val) or val is None:
                        values.append('NULL')
                    elif isinstance(val, str):
                        clean_val = val.replace("'", "''")
                        values.append(f"'{clean_val}'")
                    else:
                        values.append(str(val))
                
                insert = f"INSERT INTO biens_immobiliers VALUES ({', '.join(values)});\n"
                f.write(insert)
    
    # ============================================
    # ANALYSES COMPLÉMENTAIRES
    # ============================================
    
    def analyser_par_quartier(self, df):
        """Analyse détaillée par quartier (pour l'indice immobilier)"""
        print("\n" + "="*60)
        print("📍 ANALYSE PAR QUARTIER")
        print("="*60)
        
        analyse = df[df['quartier'] != 'Non spécifié'].groupby('quartier').agg({
            'prix_m2': ['mean', 'median', 'min', 'max', 'count'],
            'surface_m2': 'mean',
            'prix_fcfa': 'mean'
        }).round(0)
        
        analyse.columns = ['Prix/m² Moyen', 'Prix/m² Médian', 'Prix/m² Min', 
                          'Prix/m² Max', 'Nb Annonces', 'Surface Moy', 'Prix Moyen']
        
        # Trier par prix au m² décroissant
        analyse = analyse.sort_values('Prix/m² Moyen', ascending=False)
        
        print(analyse)
        return analyse
    
    def detecter_anomalies(self, df):
        """Détecter les prix aberrants (pour validation)"""
        print("\n" + "="*60)
        print("🔍 DÉTECTION DES ANOMALIES")
        print("="*60)
        
        Q1 = df['prix_m2'].quantile(0.25)
        Q3 = df['prix_m2'].quantile(0.75)
        IQR = Q3 - Q1
        
        # Bornes IQR (méthode standard)
        borne_inf = Q1 - 1.5 * IQR
        borne_sup = Q3 + 1.5 * IQR
        
        anomalies = df[(df['prix_m2'] < borne_inf) | (df['prix_m2'] > borne_sup)]
        
        print(f"Nombre d'anomalies détectées: {len(anomalies)}")
        print(f"Borne inférieure: {borne_inf:,.0f} FCFA/m²")
        print(f"Borne supérieure: {borne_sup:,.0f} FCFA/m²")
        
        if len(anomalies) > 0:
            print("\nExemples d'anomalies:")
            print(anomalies[['titre_complet', 'quartier', 'prix_m2', 'prix_fcfa', 'surface_m2']].head(10))
        
        return anomalies


# ============================================
# FONCTION PRINCIPALE D'UTILISATION
# ============================================

def main():
    """
    Fonction principale pour nettoyer les données Facebook Marketplace
    """
    
    print("="*60)
    print("🏠 PROJET ID IMMOBILIER - NETTOYAGE DES DONNÉES")
    print("="*60)
    print()
    
    # 1. Charger les données
    print("📂 Chargement des données...")
    df = pd.read_csv('/mnt/user-data/uploads/1770856556826_dataset_test_2026-02-12_00-27-35-233.csv')
    print(f"   ✓ {len(df)} lignes chargées\n")
    
    # 2. Initialiser le nettoyeur
    cleaner = IDImmobilierCleaner()
    
    # 3. Nettoyer les données
    df_clean = cleaner.nettoyer_dataset(df)
    
    # 4. Analyses complémentaires
    if len(df_clean) > 0:
        # Analyse par quartier
        analyse_quartier = cleaner.analyser_par_quartier(df_clean)
        
        # Détection des anomalies
        anomalies = cleaner.detecter_anomalies(df_clean)
        
        # 5. Exports multiples
        print("\n" + "="*60)
        print("💾 EXPORTS")
        print("="*60)
        
        cleaner.exporter_pour_bdd(df_clean, format='csv')
        cleaner.exporter_pour_bdd(df_clean, format='excel')
        cleaner.exporter_pour_bdd(df_clean, format='json')
        cleaner.exporter_pour_bdd(df_clean, format='sql')
        
        # 6. Résumé final
        print("\n" + "="*60)
        print("✅ NETTOYAGE TERMINÉ")
        print("="*60)
        print(f"📊 Données valides: {len(df_clean)}/{len(df)} ({len(df_clean)/len(df)*100:.1f}%)")
        print(f"📍 Quartiers identifiés: {(df_clean['quartier'] != 'Non spécifié').sum()}")
        print(f"💰 Prix moyen au m²: {df_clean['prix_m2'].mean():,.0f} FCFA")
        print("="*60)
    
    else:
        print("\n⚠️ ATTENTION: Aucune donnée valide après nettoyage")
        print("Vérifiez vos données sources et les patterns d'extraction")


if __name__ == "__main__":
    main()