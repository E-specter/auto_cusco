/**
 * A native `select` filled from the options `lib/campos.ts` gives: `[valor, texto, grupo?]`. An option with
 * a group goes inside its `optgroup`, which a native `select` reads out loud and shows the same in every browser.
 */

export type OpcionDeLista = [string, string, string?];

export function llenarSelect(select: HTMLSelectElement, opciones: readonly OpcionDeLista[], valor: string): void {
  const grupos = new Map<string, HTMLOptGroupElement>();
  select.replaceChildren(
    ...opciones.flatMap(([value, texto, grupo]) => {
      const opcion = document.createElement('option');
      opcion.value = value;
      opcion.textContent = texto;
      opcion.selected = value === valor;
      if (!grupo) return [opcion];
      const existente = grupos.get(grupo);
      if (existente) {
        existente.append(opcion);
        return [];
      }
      const contenedor = document.createElement('optgroup');
      contenedor.label = grupo;
      contenedor.append(opcion);
      grupos.set(grupo, contenedor);
      return [contenedor];
    }),
  );
}
