import { useState } from 'react';
import { Search } from 'lucide-react';

/**
 * SearchInput - Input de búsqueda global en tiempo real.
 * Filtra por nombre, cédula o ID mediante el callback onSearch.
 */
export default function SearchInput({ placeholder, onSearch, debounceMs = 300 }) {
  const [value, setValue] = useState('');

  const handleChange = (e) => {
    setValue(e.target.value);
    onSearch(e.target.value);
  };

  return (
    <div className="relative">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
      <input
        type="text"
        value={value}
        onChange={handleChange}
        placeholder={placeholder || 'Buscar por nombre, cédula o ID...'}
        className="input-field pl-10"
      />
    </div>
  );
}