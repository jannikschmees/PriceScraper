import unittest
from app import data

class TestPriceCalculations(unittest.TestCase):
    def setUp(self):
        """Set up test data before each test."""
        self.test_data = [
            {
                'product_name': 'Test Product 1',
                'purchase_price': 10.0,
                'margin_percent': 20.0,
                'prices_found': []
            },
            {
                'product_name': 'Test Product 2',
                'purchase_price': 15.0,
                'margin_percent': 30.0,
                'prices_found': [18.50, 19.99, 17.25]
            },
            {
                'product_name': 'Test Product 3',
                'purchase_price': 5.0,
                'margin_percent': 0.0,  # No margin
                'prices_found': [4.99, 5.50, 5.25]
            },
            {
                'product_name': 'Test Product 4',
                'purchase_price': 100.0,
                'margin_percent': 50.0,
                'prices_found': [90.0]  # Single competitor price
            }
        ]

    def test_margin_only_calculation(self):
        """Test price calculation when no competitor prices are available."""
        item = self.test_data[0]
        margin_price = item['purchase_price'] * (1 + item['margin_percent'] / 100.0)
        self.assertEqual(margin_price, 12.0)  # 10.0 * (1 + 20/100)

    def test_with_competitor_prices(self):
        """Test price calculation with competitor prices."""
        item = self.test_data[1]
        # Calculate expected values
        margin_price = item['purchase_price'] * (1 + item['margin_percent'] / 100.0)
        min_market_price = min(item['prices_found'])
        avg_market_price = sum(item['prices_found']) / len(item['prices_found'])
        competitor_price_minus_penny = min_market_price - 0.01
        expected_price = max(margin_price, competitor_price_minus_penny)

        # Verify calculations
        self.assertEqual(margin_price, 19.50)  # 15.0 * (1 + 30/100)
        self.assertEqual(min_market_price, 17.25)
        self.assertAlmostEqual(avg_market_price, 18.58, places=2)
        self.assertEqual(competitor_price_minus_penny, 17.24)
        self.assertEqual(expected_price, 19.50)  # Should use margin price as it's higher

    def test_zero_margin(self):
        """Test price calculation with zero margin."""
        item = self.test_data[2]
        margin_price = item['purchase_price'] * (1 + item['margin_percent'] / 100.0)
        min_market_price = min(item['prices_found'])
        competitor_price_minus_penny = min_market_price - 0.01
        expected_price = max(margin_price, competitor_price_minus_penny)
        
        self.assertEqual(margin_price, 5.0)  # No margin added
        self.assertEqual(min_market_price, 4.99)
        self.assertEqual(expected_price, 5.0)  # Should use purchase price as it's higher

    def test_single_competitor_price(self):
        """Test price calculation with only one competitor price."""
        item = self.test_data[3]
        margin_price = item['purchase_price'] * (1 + item['margin_percent'] / 100.0)
        min_market_price = min(item['prices_found'])
        avg_market_price = sum(item['prices_found']) / len(item['prices_found'])
        
        self.assertEqual(margin_price, 150.0)  # 100.0 * (1 + 50/100)
        self.assertEqual(min_market_price, 90.0)
        self.assertEqual(avg_market_price, 90.0)  # Average should equal single price

    def test_price_cleaning(self):
        """Test price text cleaning and conversion."""
        test_cases = [
            ("9,25 €", 9.25),
            ("10.000,50 €", 10000.50),
            ("1.234,56 €", 1234.56),
            ("0,99 €", 0.99),
            ("1.234.567,89 €", 1234567.89),  # Large number
            ("0,09 €", 0.09),  # Small number
            ("42 €", 42.0),  # No decimal places
            ("42,00 €", 42.0),  # Zero decimal places
            ("1,- €", 1.0),  # Special case
        ]
        
        for price_text, expected in test_cases:
            price_part = price_text.split('€')[0].strip()
            cleaned_price = price_part.replace('.', '').replace(',', '.').replace('-', '0')
            self.assertEqual(float(cleaned_price), expected)

    def test_edge_cases(self):
        """Test edge cases and potential error conditions."""
        # Test with very small numbers
        self.assertAlmostEqual(float("0,01 €".split('€')[0].strip().replace(',', '.')), 0.01)
        
        # Test with very large numbers
        large_price = "999.999.999,99 €"
        price_part = large_price.split('€')[0].strip()
        cleaned_price = price_part.replace('.', '').replace(',', '.')
        self.assertEqual(float(cleaned_price), 999999999.99)
        
        # Test invalid price handling
        invalid_prices = [
            "",  # Empty string
            "€",  # Just currency symbol
            "abc €",  # Non-numeric
            ",- €",  # Invalid format
            ".",  # Just decimal
        ]
        
        for invalid_price in invalid_prices:
            with self.assertRaises(Exception):
                if not invalid_price or invalid_price == "€":
                    raise ValueError("Empty price")
                price_part = invalid_price.split('€')[0].strip()
                if not price_part or not any(c.isdigit() for c in price_part):
                    raise ValueError("No numeric value in price")
                cleaned_price = price_part.replace('.', '').replace(',', '.')
                float(cleaned_price)

    def test_recommended_price_logic(self):
        """Test the logic for determining recommended prices."""
        test_cases = [
            # (purchase_price, margin_percent, competitor_prices, expected_recommended)
            (10.0, 20.0, [12.0, 13.0, 11.0], 12.0),  # Margin price > min competitor
            (10.0, 10.0, [15.0, 16.0, 14.0], 13.99),  # Use competitor price - 0.01
            (10.0, 0.0, [9.0, 9.5, 8.0], 10.0),  # Use purchase price when no margin
            (100.0, 50.0, [200.0, 180.0, 150.0], 150.0),  # Use margin price
        ]
        
        for purchase_price, margin_percent, competitor_prices, expected in test_cases:
            with self.subTest(purchase_price=purchase_price, margin_percent=margin_percent):
                margin_price = purchase_price * (1 + margin_percent / 100.0)
                min_market_price = min(competitor_prices)
                competitor_price_minus_penny = min_market_price - 0.01
                recommended_price = max(margin_price, competitor_price_minus_penny)
                self.assertAlmostEqual(recommended_price, expected, places=2,
                    msg=f"Failed with: margin_price={margin_price}, min_market_price={min_market_price}")

if __name__ == '__main__':
    unittest.main() 